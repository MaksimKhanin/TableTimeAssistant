import asyncio
import json
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

import models
import schemas
from schemas import CharacterPresetCreate, CharacterPresetOut
import dnd
import roll_directive
import referee
import llm as llm_client
from database import get_db, init_db
from referee import DEFAULT_REFEREE_DECIDE_SYSTEM, DEFAULT_REFEREE_ANALYZE_SYSTEM
from prompts_config import NARRATION_USER_TURN_TEMPLATE

app = FastAPI(title="DnD Game Master", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.on_event("startup")
def startup():
    init_db()


# ── Adventures ──────────────────────────────────────────────────────────────

@app.post("/api/adventures", response_model=schemas.AdventureOut)
def create_adventure(data: schemas.AdventureCreate, db: Session = Depends(get_db)):
    if len(data.characters) != data.player_count:
        raise HTTPException(400, "Количество персонажей должно совпадать с player_count")
    if data.player_count > 4:
        raise HTTPException(400, "Максимум 4 игрока")

    adventure = models.Adventure(
        title=data.title,
        description=data.description,
        gm_role=data.gm_role,
        player_count=data.player_count,
    )
    db.add(adventure)
    db.flush()

    for c in data.characters:
        char = models.Character(adventure_id=adventure.id, **c.model_dump())
        char.current_hp = char.max_hp
        db.add(char)

    for n in data.npcs:
        npc = models.Npc(adventure_id=adventure.id, **n.model_dump())
        npc.current_hp = npc.max_hp
        db.add(npc)

    db.commit()
    db.refresh(adventure)
    return adventure


@app.get("/api/adventures", response_model=list[schemas.AdventureOut])
def list_adventures(db: Session = Depends(get_db)):
    return db.query(models.Adventure).order_by(models.Adventure.created_at.desc()).all()


@app.get("/api/adventures/{adventure_id}", response_model=schemas.AdventureOut)
def get_adventure(adventure_id: int, db: Session = Depends(get_db)):
    a = db.get(models.Adventure, adventure_id)
    if not a:
        raise HTTPException(404, "Приключение не найдено")
    return a


@app.delete("/api/adventures/{adventure_id}")
def delete_adventure(adventure_id: int, db: Session = Depends(get_db)):
    a = db.get(models.Adventure, adventure_id)
    if not a:
        raise HTTPException(404, "Приключение не найдено")
    db.delete(a)
    db.commit()
    return {"ok": True}


# ── Messages ─────────────────────────────────────────────────────────────────

@app.get("/api/adventures/{adventure_id}/messages", response_model=list[schemas.MessageOut])
def get_messages(adventure_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Message)
        .filter(models.Message.adventure_id == adventure_id)
        .order_by(models.Message.created_at)
        .all()
    )


# ── Player Dice Rolls ─────────────────────────────────────────────────────────

_STAT_LABEL = {"str": "СИЛ", "dex": "ЛОВ", "wis": "МДР", "cha": "ХАР"}


def _char_stat(char, code: str) -> int:
    return {
        "str": char.strength,
        "dex": char.dexterity,
        "wis": char.wisdom,
        "cha": char.charisma,
    }.get(code, char.strength)


def _resolve_char_roll(char, roll_type, target_ac=None, damage_dice=None,
                       manual_die=None, manual_total=None):
    """Resolve a player roll using the 4-attribute custom system."""
    if roll_type == "initiative":
        r = dnd.roll_initiative(char.dexterity, die=manual_die)
        return dnd.format_roll_result(r, f"Инициатива {char.name}"), {"type": "initiative", **r}

    if roll_type in ("attack", "phys_attack"):
        r = dnd.roll_phys_attack(char.phys_attack_bonus, die=manual_die)
        hit = target_ac is None or r["total"] >= target_ac
        text = dnd.format_roll_result(r, f"Физ. атака {char.name}")
        if target_ac is not None:
            text += f" vs Физ. защита {target_ac} → {'**ПОПАДАНИЕ**' if hit else 'промах'}"
        if hit and not r["critical"]:
            text += " (обычный удар, НЕ критический)"
        return text, {**r, "hit": hit}

    if roll_type == "mag_attack":
        r = dnd.roll_mag_attack(char.mag_attack_bonus, die=manual_die)
        hit = target_ac is None or r["total"] >= target_ac
        text = dnd.format_roll_result(r, f"Маг. атака {char.name}")
        if target_ac is not None:
            text += f" vs Сложность {target_ac} → {'**ДОСТИГНУТ**' if hit else 'провал'}"
        return text, {**r, "hit": hit}

    if roll_type == "mental_attack":
        r = dnd.roll_mental_attack(char.mental_attack_bonus, die=manual_die)
        hit = target_ac is None or r["total"] >= target_ac
        text = dnd.format_roll_result(r, f"Мент. атака {char.name}")
        if target_ac is not None:
            text += f" vs Мент. защита {target_ac} → {'**УСПЕХ**' if hit else 'провал'}"
        return text, {**r, "hit": hit}

    if roll_type == "damage":
        dice = damage_dice or char.damage_dice
        modifier = char.strength // 2
        r = dnd.roll_damage(dice, modifier, manual_total=manual_total)
        return dnd.format_roll_result(r, f"Урон {char.name}"), r

    if roll_type == "mag_damage":
        dice = damage_dice or "1d6"
        r = dnd.roll_damage(dice, manual_total=manual_total)
        return dnd.format_roll_result(r, f"Маг. урон {char.name}"), r

    if roll_type.startswith("save_"):
        suffix = roll_type[5:]  # phys | mag | mental
        defense_map = {
            "phys": (char.phys_defense, "Физ. защита"),
            "mag": (char.mag_defense, "Маг. защита"),
            "mental": (char.mental_defense, "Мент. защита"),
            # legacy stat saves → map to nearest defense
            "str": (char.phys_defense, "Физ. защита"),
            "dex": (char.phys_defense, "Физ. защита"),
            "wis": (char.mag_defense, "Маг. защита"),
            "cha": (char.mental_defense, "Мент. защита"),
        }
        defense, label = defense_map.get(suffix, (char.phys_defense, "Физ. защита"))
        dc = target_ac if target_ac is not None else 12
        r = dnd.roll_saving_throw(defense, dc, die=manual_die)
        text = (
            f"**Спасбросок {label} {char.name}**: 🎲 d20={r['die']} + {r['modifier']} = **{r['total']}**"
            f" vs DC {dc} → {'✅ Успех' if r['success'] else '❌ Провал'}"
        )
        return text, r

    if roll_type.startswith("check_"):
        code = roll_type[6:]  # str | dex | wis | cha
        stat = _char_stat(char, code)
        dc = target_ac if target_ac is not None else 12
        r = dnd.roll_ability_check(stat, dc, die=manual_die)
        label = _STAT_LABEL.get(code, code.upper())
        text = (
            f"**Проверка {label} {char.name}**: 🎲 d20={r['die']} + {r['modifier']} = **{r['total']}**"
            f" vs DC {dc} → {'✅ Успех' if r['success'] else '❌ Провал'}"
        )
        return text, r

    sides = int(roll_type.replace("d", "") or 20)
    val = manual_total if manual_total is not None else dnd.roll(sides)[0]
    return f"🎲 d{sides} = **{val}**", {"total": val}


def _resolve_npc_roll(npc, roll_type, target_ac=None, damage_dice=None,
                      manual_die=None, manual_total=None):
    """Resolve an NPC/enemy roll using direct defense values stored on the NPC."""
    if roll_type in ("attack", "phys_attack"):
        r = dnd.roll_phys_attack(npc.attack_bonus, die=manual_die)
        hit = target_ac is None or r["total"] >= target_ac
        text = dnd.format_roll_result(r, f"Физ. атака {npc.name}")
        if target_ac is not None:
            text += f" vs Физ. защита {target_ac} → {'**ПОПАДАНИЕ**' if hit else 'промах'}"
        if hit and not r["critical"]:
            text += " (обычный удар, НЕ критический)"
        return text, {**r, "hit": hit}

    if roll_type in ("mag_attack", "mental_attack"):
        r = dnd.roll_phys_attack(npc.attack_bonus, die=manual_die)
        hit = target_ac is None or r["total"] >= target_ac
        label = "Маг." if roll_type == "mag_attack" else "Мент."
        text = dnd.format_roll_result(r, f"{label} атака {npc.name}")
        if target_ac is not None:
            text += f" → {'**УСПЕХ**' if hit else 'провал'}"
        return text, {**r, "hit": hit}

    if roll_type == "damage":
        dice = damage_dice or npc.damage_dice
        r = dnd.roll_damage(dice, manual_total=manual_total)
        return dnd.format_roll_result(r, f"Урон {npc.name}"), r

    if roll_type == "initiative":
        d = dnd._d20(manual_die)
        return f"**Инициатива {npc.name}**: 🎲 d20 = **{d}**", {"type": "initiative", "die": d, "total": d}

    if roll_type.startswith("save_"):
        suffix = roll_type[5:]
        defense_map = {
            "phys": (npc.phys_defense, "Физ. защита"),
            "mag": (npc.mag_defense, "Маг. защита"),
            "mental": (npc.mental_defense, "Мент. защита"),
        }
        defense, label = defense_map.get(suffix, (npc.phys_defense, "Физ. защита"))
        dc = target_ac if target_ac is not None else 12
        r = dnd.roll_saving_throw(defense, dc, die=manual_die)
        text = (
            f"**Спасбросок {label} {npc.name}**: 🎲 d20={r['die']} + {r['modifier']} = **{r['total']}**"
            f" vs DC {dc} → {'✅ Успех' if r['success'] else '❌ Провал'}"
        )
        return text, r

    if roll_type.startswith("check_"):
        code = roll_type[6:]
        mod = 2
        dc = target_ac if target_ac is not None else 12
        d = dnd._d20(manual_die)
        total = d + mod
        success = total >= dc
        label = _STAT_LABEL.get(code, code.upper())
        text = (
            f"**Проверка {label} {npc.name}**: 🎲 d20={d} + {mod} = **{total}**"
            f" vs DC {dc} → {'✅ Успех' if success else '❌ Провал'}"
        )
        return text, {"die": d, "modifier": mod, "total": total, "dc": dc, "success": success}

    sides = int(roll_type.replace("d", "") or 20)
    val = manual_total if manual_total is not None else dnd.roll(sides)[0]
    return f"🎲 {npc.name} d{sides} = **{val}**", {"total": val}


def _resolve_actor(adventure, name: str):
    """Match a roll's actor name to a concrete entity.
    Returns ("char", obj) | ("npc", obj) | (None, None)."""
    if not name:
        return None, None
    want = name.strip().lower()
    chars = list(adventure.characters)
    npcs = list(adventure.npcs)
    # Exact (case-insensitive) first, then prefix/contains.
    for matcher in (
        lambda n: n == want,
        lambda n: n.startswith(want) or want.startswith(n),
        lambda n: want in n or n in want,
    ):
        for c in chars:
            if matcher(c.name.strip().lower()):
                return "char", c
        for n in npcs:
            if matcher(n.name.strip().lower()):
                return "npc", n
    return None, None


@app.get("/api/char-rules")
def char_rules():
    """Point-buy limits for character creation (no levels)."""
    return {
        "stat_keys": dnd.STAT_KEYS,
        "stat_min": dnd.STAT_MIN,
        "stat_max": dnd.STAT_MAX,
        "point_budget": dnd.POINT_BUDGET,
    }


@app.post("/api/adventures/{adventure_id}/roll")
def dice_roll(adventure_id: int, req: schemas.DiceRollRequest, db: Session = Depends(get_db)):
    char = db.get(models.Character, req.character_id)
    if not char or char.adventure_id != adventure_id:
        raise HTTPException(404, "Персонаж не найден")
    result_text, roll_data = _resolve_char_roll(char, req.roll_type, req.target_ac, req.damage_dice)
    db.add(models.Message(
        adventure_id=adventure_id, role="dice",
        content=result_text, player_name=char.name, metadata_=roll_data,
    ))
    db.commit()
    return {"result": result_text, "data": roll_data}


# ── NPC Dice Rolls ────────────────────────────────────────────────────────────

@app.post("/api/adventures/{adventure_id}/npc-roll")
def npc_dice_roll(adventure_id: int, req: schemas.NpcRollRequest, db: Session = Depends(get_db)):
    npc = db.get(models.Npc, req.npc_id)
    if not npc or npc.adventure_id != adventure_id:
        raise HTTPException(404, "NPC не найден")

    text, roll_data = _resolve_npc_roll(npc, req.roll_type, req.target_ac, req.damage_dice)

    db.add(models.Message(
        adventure_id=adventure_id, role="dice",
        content=text, player_name=npc.name, metadata_=roll_data,
    ))
    db.commit()
    return {"result": text, "data": roll_data}


# ── HP Management ─────────────────────────────────────────────────────────────

@app.post("/api/adventures/{adventure_id}/hp")
def update_hp(adventure_id: int, req: schemas.HPUpdateRequest, db: Session = Depends(get_db)):
    char = db.get(models.Character, req.character_id)
    if not char or char.adventure_id != adventure_id:
        raise HTTPException(404, "Персонаж не найден")
    char.current_hp = max(0, min(char.max_hp, char.current_hp + req.delta))
    char.status = "unconscious" if char.current_hp == 0 else "alive"
    db.commit()
    return {"character_id": char.id, "name": char.name, "current_hp": char.current_hp, "max_hp": char.max_hp, "status": char.status}


@app.post("/api/adventures/{adventure_id}/npc-hp")
def update_npc_hp(adventure_id: int, req: schemas.NpcHPUpdateRequest, db: Session = Depends(get_db)):
    npc = db.get(models.Npc, req.npc_id)
    if not npc or npc.adventure_id != adventure_id:
        raise HTTPException(404, "NPC не найден")
    npc.current_hp = max(0, min(npc.max_hp, npc.current_hp + req.delta))
    npc.status = "dead" if npc.current_hp == 0 else "alive"
    db.commit()
    return {"npc_id": npc.id, "name": npc.name, "current_hp": npc.current_hp, "max_hp": npc.max_hp, "status": npc.status}


# ── Templates ─────────────────────────────────────────────────────────────────

@app.get("/api/templates", response_model=list[schemas.TemplateOut])
def list_templates(db: Session = Depends(get_db)):
    return db.query(models.AdventureTemplate).order_by(
        models.AdventureTemplate.is_builtin.desc(),
        models.AdventureTemplate.id,
    ).all()


@app.post("/api/templates", response_model=schemas.TemplateOut)
def save_template(req: schemas.TemplateSaveRequest, db: Session = Depends(get_db)):
    if req.adventure_id:
        adv = db.get(models.Adventure, req.adventure_id)
        if not adv:
            raise HTTPException(404, "Приключение не найдено")
        chars = [
            {k: getattr(c, k) for k in [
                "name", "race", "char_class", "strength", "dexterity", "wisdom", "charisma",
                "max_hp", "phys_defense", "mag_defense", "mental_defense",
                "phys_attack_bonus", "mag_attack_bonus", "mental_attack_bonus",
                "damage_dice", "abilities", "background",
            ]}
            for c in adv.characters
        ]
        npcs = [
            {k: getattr(n, k) for k in [
                "name", "role", "personality", "voice_style",
                "max_hp", "phys_defense", "mag_defense", "mental_defense",
                "attack_bonus", "damage_dice", "is_enemy",
            ]}
            for n in adv.npcs
        ]
        tmpl = models.AdventureTemplate(
            title=req.title,
            category=req.category,
            description=adv.description,
            gm_role=adv.gm_role,
            player_count=adv.player_count,
            characters_json=chars,
            npcs_json=npcs,
            is_builtin=False,
        )
    else:
        tmpl = models.AdventureTemplate(
            title=req.title,
            category=req.category,
            description=req.description,
            gm_role=req.gm_role,
            player_count=req.player_count,
            characters_json=req.characters_json,
            npcs_json=req.npcs_json,
            is_builtin=False,
        )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@app.delete("/api/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    tmpl = db.get(models.AdventureTemplate, template_id)
    if not tmpl:
        raise HTTPException(404, "Шаблон не найден")
    if tmpl.is_builtin:
        raise HTTPException(400, "Встроенные шаблоны нельзя удалить")
    db.delete(tmpl)
    db.commit()
    return {"ok": True}


# ── Prompt Config ─────────────────────────────────────────────────────────────

def _prompt_config_dict(cfg) -> dict:
    return {
        "system_addendum": cfg.system_addendum or "",
        "turn_reminder": cfg.turn_reminder or "",
        "roll_enforcement": bool(cfg.roll_enforcement),
        "roll_rules": cfg.roll_rules_json or roll_directive.DEFAULT_ROLL_RULES,
        "hp_tracking": bool(cfg.hp_tracking),
        "referee_decide_system": cfg.referee_decide_system or "",
        "referee_analyze_system": cfg.referee_analyze_system or "",
    }


@app.get("/api/prompt-config/defaults")
def get_prompt_defaults():
    """Return the built-in default values so the UI can reset to them."""
    return {
        "system_addendum": llm_client.DEFAULT_SYSTEM_ADDENDUM,
        "turn_reminder": llm_client.DEFAULT_TURN_REMINDER,
        "roll_enforcement": True,
        "roll_rules": roll_directive.DEFAULT_ROLL_RULES,
        "hp_tracking": True,
        "referee_decide_system": DEFAULT_REFEREE_DECIDE_SYSTEM,
        "referee_analyze_system": DEFAULT_REFEREE_ANALYZE_SYSTEM,
    }


@app.get("/api/prompt-config")
def get_prompt_config(db: Session = Depends(get_db)):
    return _prompt_config_dict(db.get(models.PromptConfig, 1))


@app.put("/api/prompt-config")
def update_prompt_config(data: schemas.PromptConfigUpdate, db: Session = Depends(get_db)):
    cfg = db.get(models.PromptConfig, 1)
    cfg.system_addendum = data.system_addendum
    cfg.turn_reminder = data.turn_reminder
    cfg.roll_enforcement = data.roll_enforcement
    cfg.roll_rules_json = [r.model_dump() for r in data.roll_rules]
    cfg.hp_tracking = data.hp_tracking
    cfg.referee_decide_system = data.referee_decide_system
    cfg.referee_analyze_system = data.referee_analyze_system
    db.commit()
    db.refresh(cfg)
    return _prompt_config_dict(cfg)


# ── Character Presets ─────────────────────────────────────────────────────────

@app.get("/api/character-presets", response_model=list[CharacterPresetOut])
def list_character_presets(db: Session = Depends(get_db)):
    return db.query(models.CharacterPreset).order_by(models.CharacterPreset.created_at.desc()).all()


_PRESET_FIELDS = {
    "name", "race", "char_class", "strength", "dexterity", "wisdom", "charisma",
    "max_hp", "phys_defense", "mag_defense", "mental_defense",
    "damage_dice", "abilities", "background",
}

@app.post("/api/character-presets", response_model=CharacterPresetOut)
def create_character_preset(data: CharacterPresetCreate, db: Session = Depends(get_db)):
    preset = models.CharacterPreset(**{k: v for k, v in data.model_dump().items() if k in _PRESET_FIELDS})
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


@app.delete("/api/character-presets/{preset_id}")
def delete_character_preset(preset_id: int, db: Session = Depends(get_db)):
    preset = db.get(models.CharacterPreset, preset_id)
    if not preset:
        raise HTTPException(404, "Пресет не найден")
    db.delete(preset)
    db.commit()
    return {"ok": True}


# ── LLM Config ────────────────────────────────────────────────────────────────

@app.get("/api/llm/config")
def get_llm_config():
    return llm_client.get_config()


@app.put("/api/llm/config")
def update_llm_config(data: schemas.LLMConfigUpdate):
    llm_client.update_config(**data.model_dump())
    return llm_client.get_config()


@app.get("/api/llm/status")
async def llm_status():
    return await llm_client.check_connection()


@app.get("/api/llm/models")
async def llm_models():
    return await llm_client.list_models()


# ── WebSocket Game Session ────────────────────────────────────────────────────

@app.websocket("/ws/{adventure_id}")
async def websocket_game(websocket: WebSocket, adventure_id: int):
    await websocket.accept()
    db = next(get_db())

    try:
        adventure = db.get(models.Adventure, adventure_id)
        if not adventure:
            await websocket.send_json({"type": "error", "message": "Приключение не найдено"})
            await websocket.close()
            return

        # Load prompt config
        prompt_cfg = db.get(models.PromptConfig, 1)
        system_addendum = prompt_cfg.system_addendum if prompt_cfg else ""
        turn_reminder = prompt_cfg.turn_reminder if prompt_cfg else ""
        roll_rules = (prompt_cfg.roll_rules_json if prompt_cfg else None) or roll_directive.DEFAULT_ROLL_RULES
        roll_enforcement = bool(prompt_cfg.roll_enforcement) if prompt_cfg else False
        hp_tracking = bool(prompt_cfg.hp_tracking) if prompt_cfg else False
        referee_decide_sys = (prompt_cfg.referee_decide_system if prompt_cfg else "") or ""
        referee_analyze_sys = (prompt_cfg.referee_analyze_system if prompt_cfg else "") or ""

        def build_chars_npcs():
            db.expire_all()
            chars = [
                {
                    "name": c.name, "race": c.race, "char_class": c.char_class,
                    "current_hp": c.current_hp, "max_hp": c.max_hp,
                    "strength": c.strength, "dexterity": c.dexterity, "wisdom": c.wisdom, "charisma": c.charisma,
                    "phys_defense": c.phys_defense, "mag_defense": c.mag_defense, "mental_defense": c.mental_defense,
                    "abilities": c.abilities, "background": c.background,
                }
                for c in adventure.characters
            ]
            npcs_data = [
                {
                    "name": n.name, "role": n.role, "personality": n.personality,
                    "voice_style": n.voice_style, "current_hp": n.current_hp,
                    "max_hp": n.max_hp, "phys_defense": n.phys_defense, "mag_defense": n.mag_defense,
                    "mental_defense": n.mental_defense, "is_enemy": n.is_enemy,
                }
                for n in adventure.npcs
            ]
            return chars, npcs_data

        chars, npcs_data = build_chars_npcs()
        system_prompt = llm_client.build_system_prompt(
            adventure.description, adventure.gm_role, chars, npcs_data, system_addendum,
            roll_rules=roll_rules, roll_enforcement=roll_enforcement, use_tools=False,
            hp_tracking=hp_tracking,
        )

        history = db.query(models.Message).filter(
            models.Message.adventure_id == adventure_id,
            models.Message.role.in_(["user", "assistant", "dice"]),
        ).order_by(models.Message.created_at).all()

        # Some model templates (e.g. Qwen3) require at least one user message.
        # If history starts with an assistant opening narration, inject the
        # silent trigger so the conversation structure is always valid.
        OPENING_TRIGGER = {"role": "user", "content": "Начни приключение."}

        messages = [{"role": "system", "content": system_prompt}]
        if history and history[0].role == "assistant":
            messages.append(OPENING_TRIGGER)
        for h in history:
            # Dice results are fed back to the model as user turns so the GM can
            # narrate consequences based on the actual outcome.
            if h.role == "dice":
                messages.append({"role": "user", "content": f"[Результат броска] {h.content}"})
            else:
                messages.append({"role": h.role, "content": h.content})

        async def _stream_to_ws(msgs: list) -> str:
            """Stream the GM turn to the client and return the cleaned narration.
            The narration model no longer decides mechanics (the referee does),
            but we still strip any stray [[...]] tokens defensively."""
            show_thinking = llm_client.get_config().get("show_thinking", False)
            think_buf = ""
            filt = roll_directive.DirectiveStreamFilter()
            async for kind, text in llm_client.stream_response(msgs):
                if kind == "think":
                    think_buf += text
                else:
                    for visible in filt.feed(text):
                        await websocket.send_json({"type": "chunk", "content": visible})
            _spec, _hp, cleaned, tail = filt.result()
            if tail:
                await websocket.send_json({"type": "chunk", "content": tail})
            if think_buf and show_thinking:
                await websocket.send_json({"type": "think_done", "content": think_buf})
            return cleaned

        async def record_dice(text: str, roll_data: dict, actor_name: str, include_state: bool = False):
            """Persist a dice result, show it to the client, feed it back to the model."""
            db.add(models.Message(
                adventure_id=adventure_id, role="dice",
                content=text, player_name=actor_name, metadata_=roll_data,
            ))
            db.commit()
            await websocket.send_json({"type": "dice_result", "content": text})
            content = f"[Roll result] {text}"
            if include_state:
                content += f"\n\n{get_state_context()}"
            messages.append({"role": "user", "content": content})

        async def apply_hp_changes(changes: list):
            """Apply model-reported damage/healing to the DB and update the UI live."""
            if not changes:
                return
            for ch in changes:
                kind, actor = _resolve_actor(adventure, ch.get("target"))
                if not actor:
                    continue
                delta = int(ch.get("delta") or 0)
                if delta == 0:
                    continue
                before = actor.current_hp
                actor.current_hp = max(0, min(actor.max_hp, before + delta))
                if kind == "npc":
                    actor.status = "dead" if actor.current_hp == 0 else "alive"
                else:
                    actor.status = "unconscious" if actor.current_hp == 0 else "alive"
                db.commit()
                sign = "💚" if delta > 0 else "💔"
                verb = f"+{delta}" if delta > 0 else str(delta)
                note = f"{sign} **{actor.name}**: {verb} ХП ({before} → {actor.current_hp})"
                if actor.current_hp == 0:
                    note += " — **повержен**" if kind == "npc" else " — **без сознания**"
                db.add(models.Message(
                    adventure_id=adventure_id, role="dice", content=note,
                    player_name=actor.name, metadata_={"hp": actor.current_hp, "delta": delta},
                ))
                db.commit()
                await websocket.send_json({
                    "type": "hp_update", "content": note,
                    "name": actor.name, "current_hp": actor.current_hp,
                    "max_hp": actor.max_hp, "status": actor.status,
                    "is_npc": kind == "npc",
                })
                messages.append({"role": "user", "content": f"[HP update] {note}"})

        async def auto_roll_npc(npc, spec: dict):
            """Enemies and NPCs roll automatically. A successful attack auto-rolls damage too."""
            rtype = spec.get("type", "save_dex")
            text, rdata = _resolve_npc_roll(npc, rtype, spec.get("dc"))
            if rtype == "attack" and rdata.get("hit"):
                await record_dice(text, rdata, npc.name)
                dtext, ddata = _resolve_npc_roll(npc, "damage", None)
                await record_dice(dtext, ddata, npc.name, include_state=True)
            else:
                await record_dice(text, rdata, npc.name, include_state=True)

        def get_state_context() -> str:
            """Compact party state block used by the referee and injected into DM turns."""
            db.expire_all()
            char_lines = [
                f"{c.name} ({c.race} {c.char_class}): {c.current_hp}/{c.max_hp} HP, ФЗ {c.phys_defense}/МЗ {c.mag_defense}/МТЗ {c.mental_defense} [{c.status}]"
                for c in adventure.characters
            ]
            npc_lines = [
                f"{n.name} ({'enemy' if n.is_enemy else 'ally'}): {n.current_hp}/{n.max_hp} HP [{n.status}]"
                for n in adventure.npcs
            ]
            parts = ["[Party state]"] + char_lines
            if npc_lines:
                parts += ["[NPCs]"] + npc_lines
            return "\n".join(parts)

        def build_dm_user_turn(player_name: str, content: str) -> str:
            """Prompt #3 — context wrapper injected as the user turn for each DM call."""
            db.expire_all()
            scene = adventure.scene_state or {}
            location = scene.get("location", "")
            objective = scene.get("objective", "")

            char_lines = [
                f"- {c.name} ({c.race} {c.char_class}): {c.current_hp}/{c.max_hp} HP, ФЗ {c.phys_defense}/МЗ {c.mag_defense}/МТЗ {c.mental_defense} [{c.status}]"
                for c in adventure.characters
            ]
            npc_lines = [
                f"- {n.name} ({'enemy' if n.is_enemy else 'ally'}): {n.current_hp}/{n.max_hp} HP [{n.status}]"
                for n in adventure.npcs
            ]
            party_block = "\n".join(char_lines)
            if npc_lines:
                party_block += "\n" + "\n".join(npc_lines)

            loc_line = f"Current location: {location}\n" if location else ""
            obj_line = f"Active objective: {objective}\n" if objective else ""
            reminder_block = f"\n\n{turn_reminder.strip()}" if turn_reminder and turn_reminder.strip() else ""

            return NARRATION_USER_TURN_TEMPLATE.format(
                title=adventure.title,
                gm_role=adventure.gm_role,
                loc_line=loc_line,
                obj_line=obj_line,
                party_block=party_block,
                player_name=player_name,
                content=content,
                reminder_block=reminder_block,
            )

        def build_referee_context() -> str:
            """Context block passed to both referee decision points (Prompts #4 & #5).
            Matches the _context_block() pattern: campaign + scene + party + recent turns."""
            db.expire_all()
            scene = adventure.scene_state or {}
            recent = db.query(models.Message).filter(
                models.Message.adventure_id == adventure_id,
                models.Message.role.in_(["user", "assistant", "dice"]),
            ).order_by(models.Message.created_at.desc()).limit(12).all()
            recent_lines = "\n".join(f"{m.role}: {m.content[:200]}" for m in reversed(recent))
            return (
                f"Campaign: {adventure.title}\n"
                f"Setting: {adventure.description[:300]}\n"
                f"GM style: {adventure.gm_role}\n"
                f"Current location: {scene.get('location', '—')}\n"
                f"Active objective: {scene.get('objective', '—')}\n\n"
                f"{get_state_context()}\n\n"
                f"Recent turns:\n{recent_lines or '—'}"
            )

        async def update_scene(scene: dict | None):
            """Persist referee scene state and push it (with clickable choices) to the UI."""
            if not scene:
                return
            adventure.scene_state = scene
            db.commit()
            await websocket.send_json({
                "type": "scene_update",
                "location": scene.get("location", ""),
                "objective": scene.get("objective", ""),
                "summary": scene.get("summary", ""),
                "choices": scene.get("choices", []),
            })

        async def gate_player_roll(spec: dict):
            """Lock the session on a player roll and prompt the client. The player
            never rolls for NPCs, so an unresolved actor falls back to PC choice."""
            spec = roll_directive.apply_default_dc(spec, roll_rules)
            _kind, actor = _resolve_actor(adventure, spec.get("actor"))
            if _kind == "npc":
                actor = None  # players pick among their own characters instead
            spec["actor_type"] = "char"
            spec["actor_id"] = actor.id if actor else None
            spec["actor_name"] = actor.name if actor else ""
            spec["locked"] = actor is not None
            adventure.pending_roll = spec
            db.commit()
            await websocket.send_json({"type": "roll_required", "spec": spec})

        async def generate_turn(msgs: list, _depth: int = 0):
            """Run one GM turn: stream the narration, persist it, then run the
            referee POST-PASS — one utility call that decides HP changes, any
            roll the narration implies (enemy attack, trap, forced save) and the
            updated scene state with clickable choices. The narration model never
            decides mechanics itself."""
            await websocket.send_json({"type": "thinking"})
            cleaned = await _stream_to_ws(msgs)
            db.add(models.Message(adventure_id=adventure_id, role="assistant", content=cleaned))
            msgs.append({"role": "assistant", "content": cleaned})

            analysis = await referee.analyze_narration(
                cleaned, build_referee_context(), roll_rules, adventure.scene_state,
                want_roll=roll_enforcement, want_hp=hp_tracking,
                system_override=referee_analyze_sys,
            )

            # Apply any HP changes the referee detected (damage / healing) before gating.
            if hp_tracking:
                await apply_hp_changes(analysis.get("hp") or [])
            await websocket.send_json({"type": "done"})

            spec = analysis.get("roll")
            if spec and roll_enforcement:
                actor_kind, actor = _resolve_actor(adventure, spec.get("actor"))
                if actor_kind == "npc":
                    # Enemies/allies auto-roll server-side, then the scene continues.
                    adventure.pending_roll = None
                    db.commit()
                    await auto_roll_npc(actor, spec)
                    if _depth < 6:
                        await generate_turn(msgs, _depth + 1)
                    return
                # A player must roll — block the session (choices wait until resolved).
                await gate_player_roll(spec)
                return

            # No roll required → publish updated scene state + clickable choices.
            adventure.pending_roll = None
            await update_scene(analysis.get("scene"))
            db.commit()

        if not history:
            messages.append(OPENING_TRIGGER)
            await generate_turn(messages)
        elif adventure.pending_roll:
            # Reconnected mid-roll — re-prompt the player for the pending roll.
            await websocket.send_json({"type": "roll_required", "spec": adventure.pending_roll})

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "message":
                # Gate: while a roll is pending, narration cannot continue.
                if adventure.pending_roll:
                    await websocket.send_json({
                        "type": "roll_required", "spec": adventure.pending_roll, "blocked": True,
                    })
                    continue

                player_name = data.get("player_name", "Игрок")
                content = data.get("content", "").strip()
                if not content:
                    continue

                db.add(models.Message(
                    adventure_id=adventure_id, role="user",
                    content=content, player_name=player_name,
                ))
                db.commit()

                messages.append({"role": "user", "content": build_dm_user_turn(player_name, content)})

                # PRE-PASS referee: decide a roll straight from the player's action,
                # BEFORE any narration. This is the decisive fix for rolls that the
                # narrative implied but never happened (or happened out of place).
                if roll_enforcement:
                    await websocket.send_json({"type": "thinking"})
                    actor_char = next(
                        (c for c in adventure.characters
                         if c.name.strip().lower() == player_name.strip().lower()),
                        None,
                    )
                    pre = await referee.decide_player_roll(
                        content, build_referee_context(),
                        actor_char.name if actor_char else player_name, roll_rules,
                        system_override=referee_decide_sys,
                    )
                    if pre:
                        narration = (pre.get("narration") or "").strip()
                        if narration:
                            db.add(models.Message(
                                adventure_id=adventure_id, role="assistant", content=narration))
                            db.commit()
                            messages.append({"role": "assistant", "content": narration})
                            await websocket.send_json({"type": "chunk", "content": narration})
                        # Lock the roll to the acting player's own character when known.
                        if actor_char:
                            pre["actor"] = actor_char.name
                        await gate_player_roll(pre)
                        continue

                await generate_turn(messages)

            elif msg_type == "roll_result":
                if not adventure.pending_roll:
                    continue

                # Players only ever roll for their own characters.
                actor_id = data.get("actor_id")
                roll_type = data.get("roll_type", "save_dex")
                dc = data.get("dc")
                manual_die = data.get("manual_die")
                manual_total = data.get("manual_total")

                actor = db.get(models.Character, actor_id)
                if not actor or actor.adventure_id != adventure_id:
                    await websocket.send_json({"type": "error", "message": "Персонаж не найден"})
                    continue
                try:
                    text, roll_data = _resolve_char_roll(
                        actor, roll_type, dc, None, manual_die, manual_total)
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": f"Ошибка броска: {e}"})
                    continue

                # Successful attack → immediately require a damage roll from the same character.
                if roll_type == "attack" and roll_data.get("hit"):
                    await record_dice(text, roll_data, actor.name)
                    dmg_spec = {
                        "actor": actor.name, "type": "damage", "dc": None,
                        "reason": f"урон от попадания ({actor.name})",
                        "actor_type": "char", "actor_id": actor.id,
                        "actor_name": actor.name, "locked": True,
                    }
                    adventure.pending_roll = dmg_spec
                    db.commit()
                    await websocket.send_json({"type": "roll_required", "spec": dmg_spec})
                else:
                    # Final roll in the chain — include state so LLM applies HP changes.
                    await record_dice(text, roll_data, actor.name, include_state=True)
                    adventure.pending_roll = None
                    db.commit()
                    await generate_turn(messages)

            elif msg_type == "cancel_roll":
                # Player chose a different action instead of rolling — lift the gate.
                if adventure.pending_roll:
                    adventure.pending_roll = None
                    db.commit()
                await websocket.send_json({"type": "roll_cancelled"})

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        db.close()


# ── Static Files ──────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")


@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
