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

def _resolve_char_roll(char, roll_type, target_ac, damage_dice):
    if roll_type == "initiative":
        r = dnd.roll_initiative(char.dexterity)
        text = dnd.format_roll_result(
            {"die": r - dnd.modifier_from_stat(char.dexterity), "bonus": dnd.modifier_from_stat(char.dexterity), "total": r},
            f"Инициатива {char.name}",
        )
        return text, {"type": "initiative", "total": r}

    if roll_type == "attack":
        r = dnd.roll_attack(char.attack_bonus)
        hit = target_ac is None or r["total"] >= target_ac
        text = dnd.format_roll_result(r, f"Атака {char.name}")
        if target_ac is not None:
            text += f" vs КД {target_ac} → {'**ПОПАДАНИЕ**' if hit else 'промах'}"
        return text, {**r, "hit": hit}

    if roll_type == "damage":
        dice = damage_dice or char.damage_dice
        r = dnd.roll_damage(dice, dnd.modifier_from_stat(char.strength))
        return dnd.format_roll_result(r, f"Урон {char.name}"), r

    if roll_type.startswith("save_"):
        stat_map = {
            "save_str": char.strength, "save_dex": char.dexterity,
            "save_con": char.constitution, "save_int": char.intelligence,
            "save_wis": char.wisdom, "save_cha": char.charisma,
        }
        stat = stat_map.get(roll_type, char.strength)
        dc = target_ac or 12
        r = dnd.roll_saving_throw(stat, dc)
        name = roll_type.replace("save_", "").upper()
        text = (
            f"**Спасбросок {name} {char.name}**: 🎲 d20={r['die']} + {r['modifier']} = **{r['total']}**"
            f" vs DC {dc} → {'✅ Успех' if r['success'] else '❌ Провал'}"
        )
        return text, r

    sides = int(roll_type.replace("d", "") or 20)
    val = dnd.roll(sides)[0]
    return f"🎲 d{sides} = **{val}**", {"total": val}


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

    if req.roll_type == "attack":
        r = dnd.roll_attack(npc.attack_bonus)
        hit = req.target_ac is None or r["total"] >= req.target_ac
        text = dnd.format_roll_result(r, f"Атака {npc.name}")
        if req.target_ac is not None:
            text += f" vs КД {req.target_ac} → {'**ПОПАДАНИЕ**' if hit else 'промах'}"
        roll_data = {**r, "hit": hit}
    elif req.roll_type == "damage":
        dice = req.damage_dice or npc.damage_dice
        r = dnd.roll_damage(dice)
        text = dnd.format_roll_result(r, f"Урон {npc.name}")
        roll_data = r
    elif req.roll_type == "initiative":
        val = dnd.roll(20)[0]
        text = f"**Инициатива {npc.name}**: 🎲 d20 = **{val}**"
        roll_data = {"type": "initiative", "total": val}
    else:
        sides = int(req.roll_type.replace("d", "") or 20)
        val = dnd.roll(sides)[0]
        text = f"🎲 {npc.name} d{sides} = **{val}**"
        roll_data = {"total": val}

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

@app.get("/api/prompt-config", response_model=schemas.PromptConfigOut)
def get_prompt_config(db: Session = Depends(get_db)):
    cfg = db.get(models.PromptConfig, 1)
    return cfg


@app.put("/api/prompt-config", response_model=schemas.PromptConfigOut)
def update_prompt_config(data: schemas.PromptConfigUpdate, db: Session = Depends(get_db)):
    cfg = db.get(models.PromptConfig, 1)
    cfg.system_addendum = data.system_addendum
    cfg.turn_reminder = data.turn_reminder
    db.commit()
    db.refresh(cfg)
    return cfg


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

        def build_chars_npcs():
            db.expire_all()
            chars = [
                {
                    "name": c.name, "race": c.race, "char_class": c.char_class,
                    "level": c.level, "current_hp": c.current_hp, "max_hp": c.max_hp,
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
        )

        history = db.query(models.Message).filter(
            models.Message.adventure_id == adventure_id,
            models.Message.role.in_(["user", "assistant"]),
        ).order_by(models.Message.created_at).all()

        # Some model templates (e.g. Qwen3) require at least one user message.
        # If history starts with an assistant opening narration, inject the
        # silent trigger so the conversation structure is always valid.
        OPENING_TRIGGER = {"role": "user", "content": "Начни приключение."}

        messages = [{"role": "system", "content": system_prompt}]
        if history and history[0].role == "assistant":
            messages.append(OPENING_TRIGGER)
        for h in history:
            messages.append({"role": h.role, "content": h.content})

        async def _stream_to_ws(msgs: list) -> str:
            show_thinking = llm_client.get_config().get("show_thinking", False)
            think_buf = ""
            full_text = ""
            async for kind, text in llm_client.stream_response(msgs):
                if kind == "think":
                    think_buf += text
                else:
                    full_text += text
                    await websocket.send_json({"type": "chunk", "content": text})
            if think_buf and show_thinking:
                await websocket.send_json({"type": "think_done", "content": think_buf})
            await websocket.send_json({"type": "done"})
            return full_text

        if not history:
            messages.append(OPENING_TRIGGER)
            await websocket.send_json({"type": "thinking"})
            full_response = await _stream_to_ws(messages)
            db.add(models.Message(adventure_id=adventure_id, role="assistant", content=full_response))
            db.commit()
            messages.append({"role": "assistant", "content": full_response})

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

                await websocket.send_json({"type": "thinking"})
                full_response = await _stream_to_ws(messages)

                db.add(models.Message(adventure_id=adventure_id, role="assistant", content=full_response))
                db.commit()
                messages.append({"role": "assistant", "content": full_response})

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
