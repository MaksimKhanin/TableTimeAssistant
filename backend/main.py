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
import dnd
import roll_directive
import llm as llm_client
from database import get_db, init_db

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

_STAT_LABEL = {"str": "СИЛ", "dex": "ЛОВ", "con": "ТЕЛ", "int": "ИНТ", "wis": "МДР", "cha": "ХАР"}


def _char_stat(char, code: str) -> int:
    return {
        "str": char.strength, "dex": char.dexterity, "con": char.constitution,
        "int": char.intelligence, "wis": char.wisdom, "cha": char.charisma,
    }.get(code, char.strength)


def _resolve_char_roll(char, roll_type, target_ac=None, damage_dice=None,
                       manual_die=None, manual_total=None):
    """Resolve a player roll. In hybrid mode the player may pass `manual_die`
    (the d20 face they physically rolled) or `manual_total` (a typed sum);
    otherwise the die is rolled randomly."""
    if roll_type == "initiative":
        r = dnd.roll_initiative(char.dexterity, die=manual_die)
        return dnd.format_roll_result(r, f"Инициатива {char.name}"), {"type": "initiative", **r}

    if roll_type == "attack":
        r = dnd.roll_attack(char.attack_bonus, die=manual_die)
        hit = target_ac is None or r["total"] >= target_ac
        text = dnd.format_roll_result(r, f"Атака {char.name}")
        if target_ac is not None:
            text += f" vs КД {target_ac} → {'**ПОПАДАНИЕ**' if hit else 'промах'}"
        if hit and not r["critical"]:
            text += " (обычный удар, НЕ критический)"
        return text, {**r, "hit": hit}

    if roll_type == "damage":
        dice = damage_dice or char.damage_dice
        r = dnd.roll_damage(dice, dnd.modifier_from_stat(char.strength), manual_total=manual_total)
        return dnd.format_roll_result(r, f"Урон {char.name}"), r

    if roll_type.startswith("save_") or roll_type.startswith("check_"):
        is_check = roll_type.startswith("check_")
        code = roll_type.split("_", 1)[1]
        stat = _char_stat(char, code)
        dc = target_ac if target_ac is not None else 12
        if is_check:
            r = dnd.roll_ability_check(stat, dc, die=manual_die)
            kind = "Проверка"
        else:
            r = dnd.roll_saving_throw(stat, dc, die=manual_die)
            kind = "Спасбросок"
        label = _STAT_LABEL.get(code, code.upper())
        text = (
            f"**{kind} {label} {char.name}**: 🎲 d20={r['die']} + {r['modifier']} = **{r['total']}**"
            f" vs DC {dc} → {'✅ Успех' if r['success'] else '❌ Провал'}"
        )
        return text, r

    sides = int(roll_type.replace("d", "") or 20)
    val = manual_total if manual_total is not None else dnd.roll(sides)[0]
    return f"🎲 d{sides} = **{val}**", {"total": val}


def _resolve_npc_roll(npc, roll_type, target_ac=None, damage_dice=None,
                      manual_die=None, manual_total=None):
    """Resolve an NPC/enemy roll. NPCs carry no ability scores, so saves and
    checks use a flat +2 modifier."""
    if roll_type == "attack":
        r = dnd.roll_attack(npc.attack_bonus, die=manual_die)
        hit = target_ac is None or r["total"] >= target_ac
        text = dnd.format_roll_result(r, f"Атака {npc.name}")
        if target_ac is not None:
            text += f" vs КД {target_ac} → {'**ПОПАДАНИЕ**' if hit else 'промах'}"
        if hit and not r["critical"]:
            text += " (обычный удар, НЕ критический)"
        return text, {**r, "hit": hit}

    if roll_type == "damage":
        dice = damage_dice or npc.damage_dice
        r = dnd.roll_damage(dice, manual_total=manual_total)
        return dnd.format_roll_result(r, f"Урон {npc.name}"), r

    if roll_type == "initiative":
        d = dnd._d20(manual_die)
        return f"**Инициатива {npc.name}**: 🎲 d20 = **{d}**", {"type": "initiative", "die": d, "total": d}

    if roll_type.startswith("save_") or roll_type.startswith("check_"):
        is_check = roll_type.startswith("check_")
        code = roll_type.split("_", 1)[1]
        mod = 2
        dc = target_ac if target_ac is not None else 12
        d = dnd._d20(manual_die)
        total = d + mod
        success = total >= dc
        label = _STAT_LABEL.get(code, code.upper())
        kind = "Проверка" if is_check else "Спасбросок"
        text = (
            f"**{kind} {label} {npc.name}**: 🎲 d20={d} + {mod} = **{total}**"
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
                "name", "race", "char_class", "level", "strength", "dexterity",
                "constitution", "intelligence", "wisdom", "charisma",
                "max_hp", "armor_class", "attack_bonus", "damage_dice", "abilities", "background",
            ]}
            for c in adv.characters
        ]
        npcs = [
            {k: getattr(n, k) for k in [
                "name", "role", "personality", "voice_style",
                "max_hp", "armor_class", "attack_bonus", "damage_dice", "is_enemy",
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
    db.commit()
    db.refresh(cfg)
    return _prompt_config_dict(cfg)


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
        use_tools = bool(llm_client.get_config().get("use_tools", False))
        active_tools = []
        if use_tools and roll_enforcement:
            active_tools += roll_directive.build_roll_tools(roll_rules)
        if use_tools and hp_tracking:
            active_tools.append(roll_directive.build_hp_tool())
        active_tools = active_tools or None

        def build_chars_npcs():
            db.expire_all()
            chars = [
                {
                    "name": c.name, "race": c.race, "char_class": c.char_class,
                    "current_hp": c.current_hp, "max_hp": c.max_hp,
                    "armor_class": c.armor_class, "abilities": c.abilities, "background": c.background,
                }
                for c in adventure.characters
            ]
            npcs_data = [
                {
                    "name": n.name, "role": n.role, "personality": n.personality,
                    "voice_style": n.voice_style, "current_hp": n.current_hp,
                    "max_hp": n.max_hp, "armor_class": n.armor_class, "is_enemy": n.is_enemy,
                }
                for n in adventure.npcs
            ]
            return chars, npcs_data

        chars, npcs_data = build_chars_npcs()
        system_prompt = llm_client.build_system_prompt(
            adventure.description, adventure.gm_role, chars, npcs_data, system_addendum,
            roll_rules=roll_rules, roll_enforcement=roll_enforcement, use_tools=use_tools,
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

        async def _stream_to_ws(msgs: list):
            """Stream the GM turn to the client, hiding ROLL/HP directives.
            Returns (cleaned_narration, roll_spec_or_None, hp_changes)."""
            show_thinking = llm_client.get_config().get("show_thinking", False)
            think_buf = ""
            tool_spec = None
            tool_hp = []
            filt = roll_directive.DirectiveStreamFilter()
            async for kind, text in llm_client.stream_response(msgs, tools=active_tools):
                if kind == "think":
                    think_buf += text
                elif kind == "roll_tool":
                    try:
                        tool_spec = roll_directive.spec_from_tool_args(json.loads(text))
                    except Exception:
                        tool_spec = None
                elif kind == "hp_tool":
                    try:
                        hp = roll_directive.hp_from_tool_args(json.loads(text))
                        if hp:
                            tool_hp.append(hp)
                    except Exception:
                        pass
                else:
                    for visible in filt.feed(text):
                        await websocket.send_json({"type": "chunk", "content": visible})
            spec, hp_changes, cleaned, tail = filt.result()
            if tail:
                await websocket.send_json({"type": "chunk", "content": tail})
            # Native tool calls take priority over inline directives.
            if tool_spec is not None:
                spec = tool_spec
            if tool_hp:
                hp_changes = tool_hp
            if think_buf and show_thinking:
                await websocket.send_json({"type": "think_done", "content": think_buf})
            # NOTE: 'done' is sent by generate_turn after HP changes are applied,
            # so HP notes appear before the turn is finalized on the client.
            return cleaned, spec, hp_changes

        async def record_dice(text: str, roll_data: dict, actor_name: str):
            """Persist a dice result, show it to the client, feed it back to the model."""
            db.add(models.Message(
                adventure_id=adventure_id, role="dice",
                content=text, player_name=actor_name, metadata_=roll_data,
            ))
            db.commit()
            await websocket.send_json({"type": "dice_result", "content": text})
            messages.append({"role": "user", "content": f"[Результат броска] {text}"})

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
                messages.append({"role": "user", "content": f"[Изменение ХП] {note}"})

        async def auto_roll_npc(npc, spec: dict):
            """Enemies and NPCs roll automatically. A successful attack auto-rolls damage too."""
            rtype = spec.get("type", "save_dex")
            text, rdata = _resolve_npc_roll(npc, rtype, spec.get("dc"))
            await record_dice(text, rdata, npc.name)
            if rtype == "attack" and rdata.get("hit"):
                dtext, ddata = _resolve_npc_roll(npc, "damage", None)
                await record_dice(dtext, ddata, npc.name)

        async def generate_turn(msgs: list, _depth: int = 0):
            """Run one GM turn: stream it, persist it, and resolve any requested roll.
            NPC rolls auto-resolve server-side (and chain into the next turn); a player
            roll blocks the session (pending_roll) and is locked to the named character."""
            await websocket.send_json({"type": "thinking"})
            cleaned, spec, hp_changes = await _stream_to_ws(msgs)
            if roll_enforcement:
                # Fall back to prose detection when the model skipped the directive.
                if spec is None:
                    spec = roll_directive.detect_roll_request(cleaned, roll_rules)
                if spec is not None:
                    spec = roll_directive.apply_default_dc(spec, roll_rules)
            db.add(models.Message(adventure_id=adventure_id, role="assistant", content=cleaned))
            msgs.append({"role": "assistant", "content": cleaned})

            # Apply any HP changes the GM reported (damage / healing) before gating.
            if hp_tracking:
                await apply_hp_changes(hp_changes)
            await websocket.send_json({"type": "done"})

            if not (spec and roll_enforcement):
                adventure.pending_roll = None
                db.commit()
                return

            actor_kind, actor = _resolve_actor(adventure, spec.get("actor"))
            if actor_kind == "npc":
                # The player never rolls for enemies/allies — auto-resolve and continue.
                adventure.pending_roll = None
                db.commit()
                await auto_roll_npc(actor, spec)
                if _depth < 6:
                    await generate_turn(msgs, _depth + 1)
                return

            # Player character (or unresolved name → player chooses among PCs).
            spec["actor_type"] = "char"
            spec["actor_id"] = actor.id if actor else None
            spec["actor_name"] = actor.name if actor else ""
            spec["locked"] = actor is not None
            adventure.pending_roll = spec
            db.commit()
            await websocket.send_json({"type": "roll_required", "spec": spec})

        if not history:
            messages.append(OPENING_TRIGGER)
            await generate_turn(messages)
        elif adventure.pending_roll:
            # Reconnected mid-roll — re-prompt the player for the pending roll.
            await websocket.send_json({"type": "roll_required", "spec": adventure.pending_roll})

        def get_state_context() -> str:
            db.expire_all()
            char_lines = [
                f"{c.name}: {c.current_hp}/{c.max_hp} ХП [{c.status}]"
                for c in adventure.characters
            ]
            npc_lines = [
                f"{n.name} ({'враг' if n.is_enemy else 'союзник'}): {n.current_hp}/{n.max_hp} ХП [{n.status}]"
                for n in adventure.npcs
            ]
            parts = ["[Состояние отряда]"] + char_lines
            if npc_lines:
                parts += ["[NPC]"] + npc_lines
            if turn_reminder and turn_reminder.strip():
                parts += [f"\n[Напоминание ГМу]: {turn_reminder.strip()}"]
            return "\n".join(parts)

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

                state = get_state_context()
                messages.append({"role": "user", "content": f"[{player_name}]: {content}\n\n{state}"})

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

                await record_dice(text, roll_data, actor.name)

                # Successful attack → immediately require a damage roll from the same character.
                if roll_type == "attack" and roll_data.get("hit"):
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
