"""Оркестрация приключения поверх БД: старт, вводная ГМ и ход игрока.

Состояние полностью в БД (никаких in-memory сессий) — приключение переживает
перезапуск и его можно продолжить. ``stream_intro``, ``play_turn`` и
``resolve_combat`` — генераторы структурных событий
(``delta``/``intent``/``scene``/``combat_ready``/``done``/``error``), которые
API-слой превращает в SSE-кадры. Сам бой ведёт ``web.simulation`` поверх
``engine.combat`` — ``combat_bridge`` только подбирает противников из каталога.
"""
from __future__ import annotations

from typing import Iterator, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import AdventureMessage, AdventureSession, Card, Character, LoreEntry
from ..enums import CardType
from . import combat_bridge, config, memory, narrator, prompts, scene
from .intent import Intent, analyze_intent
from .llm import LLMError, client_for

# типы карточек, которые при заземлении становятся «предметами» сцены
_ITEM_TYPES = {CardType.ITEM.value, CardType.WEAPON.value, CardType.ARMOR.value}
_NPC_TYPES = {CardType.CREATURE.value, CardType.CHARACTER.value}
# сторона противников в боевом движке (см. ``web/simulation.py`` ENEMY_SIDE)
_ENEMY_SIDE = "enemy"


# ───────────────────────── старт приключения ─────────────────────────


def start_adventure(
    session: Session,
    *,
    description: str,
    character_ids: list[int],
    goal: str,
    adventure_type: str = "custom",
    title: str = "",
) -> AdventureSession:
    """Создать сессию приключения с выбранной партией и зафиксировать промт ГМ."""
    chars = (
        session.execute(select(Character).where(Character.id.in_(character_ids))).scalars().all()
        if character_ids
        else []
    )
    if not chars:
        raise ValueError("нужно выбрать хотя бы одного персонажа")

    adv = AdventureSession(
        title=title.strip() or (adventure_type or "Приключение"),
        description=description.strip(),
        adventure_type=(adventure_type or "custom").strip(),
        goal=goal.strip(),
        status="active",
    )
    adv.party = list(chars)
    session.add(adv)
    session.flush()  # нужен id для промта/пинов
    adv.system_prompt = prompts.build_system_prompt(adv)
    session.commit()
    return adv


# ───────────────────────── заземление (RAG) ─────────────────────────


def _search(session: Session, queries: list[str], top_k: int) -> list[dict]:
    """Семантический поиск по нескольким запросам, слитый по карточке (best-effort)."""
    try:
        from . import retrieval
    except Exception:  # noqa: BLE001
        return []
    merged: dict[int, dict] = {}
    for query in queries:
        try:
            hits = retrieval.semantic_search(session, query, top_k=top_k)
        except Exception:  # noqa: BLE001 - эмбеддер недоступен → без заземления
            continue
        for hit in hits:
            card = hit["card"]
            prev = merged.get(card.id)
            if prev is None or hit["score"] > prev["score"]:
                merged[card.id] = hit
    results = sorted(merged.values(), key=lambda h: h["score"], reverse=True)
    return results[:top_k]


def _apply_grounding(session: Session, adv: AdventureSession, results: list[dict]) -> list[LoreEntry]:
    """Закрепить найденные NPC/локации/предметы в сцене; вернуть лор-факты."""
    lore_facts: list[LoreEntry] = []
    location_set = adv.current_location_card_id is not None
    for hit in results:
        card = hit["card"]
        if isinstance(card, LoreEntry):
            if card.category == "location" and not location_set:
                scene.set_location(session, adv, card)
                location_set = True
            else:
                lore_facts.append(card)
        elif card.card_type in _NPC_TYPES:
            # сопартийцев (игровых персонажей) не закрепляем как NPC сцены
            if getattr(card, "is_player", False):
                continue
            scene.pin_card(session, adv, card, scene.KIND_NPC)
        elif card.card_type in _ITEM_TYPES:
            scene.pin_card(session, adv, card, scene.KIND_ITEM)
    session.flush()
    return lore_facts


# ───────────────────────── вводная ГМ ─────────────────────────


def stream_intro(session: Session, adv: AdventureSession) -> Iterator[dict]:
    """Сгенерировать и сохранить вводную ГМ (поток событий)."""
    mem_cfg = config.get_section(session, "memory")
    embed_model = config.get_section(session, "embedder")["model"]
    narrator_client = client_for(session, "narrator")

    seed_query = f"{adv.description}. {adv.goal}".strip(". ")
    results = _search(session, [seed_query] if seed_query else [], int(mem_cfg["retrieval_top_k"]))
    lore_facts = _apply_grounding(session, adv, results)

    active = scene.collect_active(adv)
    context = prompts.build_context_block(
        running_summary="",
        location=active["location"],
        npcs=active["npcs"],
        items=active["items"],
        lore_facts=lore_facts,
        episodic=[],
        enrichment="",
    )
    kickoff = (
        "Начни приключение: дай яркую вводную как ГМ, опираясь на завязку, главную цель и факты "
        "мира. Опиши, где оказалась партия и что вокруг, и заверши приглашением к действию."
    )
    messages = narrator.build_messages(adv, context, [], kickoff=kickoff)

    text = yield from _stream_and_collect(narrator_client, messages)

    gm_msg = _save_message(session, adv, role="gm", content=text)
    memory.record_turn(session, adv, gm_msg, model_name=embed_model)
    session.commit()

    yield {"type": "scene", "scene": scene.serialize_scene(adv)}
    yield {"type": "done", "message_id": gm_msg.id}


# ───────────────────────── ход игрока ─────────────────────────


def play_turn(
    session: Session, adv: AdventureSession, character_id: Optional[int], text: str
) -> Iterator[dict]:
    """Обработать реплику игрока и выдать ответ ГМ (поток событий)."""
    text = (text or "").strip()
    if not text:
        yield {"type": "error", "error": "пустое сообщение"}
        return

    mem_cfg = config.get_section(session, "memory")
    embed_model = config.get_section(session, "embedder")["model"]
    narrator_client = client_for(session, "narrator")
    system_client = client_for(session, "system")

    speaker = session.get(Character, character_id) if character_id else None
    speaker_name = speaker.name if speaker is not None else "Игрок"

    # 1. зафиксировать реплику игрока
    player_msg = _save_message(
        session, adv, role="player", content=text, speaker_id=character_id
    )

    # 2. интент-анализ (системная LLM)
    intent = analyze_intent(system_client, memory.history_brief(adv), speaker_name, text)
    player_msg.intent_json = intent.to_dict()
    session.flush()
    yield {"type": "intent", "intent": intent.to_dict()}

    # 3. зачистка сцены при уходе из локации
    if intent.leaves_location:
        scene.clear_npcs(session, adv)

    # 4. заземление (RAG): закрепить найденные сущности
    queries = intent.search_queries or [text]
    results = _search(session, queries, int(mem_cfg["retrieval_top_k"]))
    lore_facts = _apply_grounding(session, adv, results)

    # 4b. подбор противников из каталога, если игрок инициирует бой
    enemy_cards: list[Card] = []
    if intent.combat_initiation:
        enemy_cards = combat_bridge.select_enemies(session, adv, intent)
        for card in enemy_cards:
            scene.pin_card(session, adv, card, scene.KIND_NPC)

    # 5. эпизодическая память + окно
    window_msgs = memory.window(adv, int(mem_cfg["window_messages"]))
    window_ids = {m.id for m in window_msgs}
    episodic = memory.episodic_recall(
        session, adv, text, top_k=int(mem_cfg["episodic_top_k"]),
        model_name=embed_model, exclude_ids=window_ids,
    )

    # 6. сборка промта (+ дообогащение по интенту)
    active = scene.collect_active(adv)
    context = prompts.build_context_block(
        running_summary=adv.running_summary,
        location=active["location"],
        npcs=active["npcs"],
        items=active["items"],
        lore_facts=lore_facts,
        episodic=episodic,
        enrichment=prompts.enrichment_for(intent, combat_ready=bool(enemy_cards)),
    )
    messages = narrator.build_messages(adv, context, window_msgs)

    # 7. потоковый ответ ГМ
    gm_text = yield from _stream_and_collect(narrator_client, messages)
    gm_msg = _save_message(session, adv, role="gm", content=gm_text)

    # 8. вектор-память + компактинг
    memory.record_turn(session, adv, player_msg, model_name=embed_model)
    memory.record_turn(session, adv, gm_msg, model_name=embed_model)
    memory.maybe_compact(session, adv, system_client, cfg=mem_cfg)
    session.commit()

    # 9. обновление сцены
    yield {"type": "scene", "scene": scene.serialize_scene(adv)}
    if enemy_cards:
        yield {
            "type": "combat_ready",
            "enemy_ids": [c.id for c in enemy_cards],
            "enemy_names": [c.name for c in enemy_cards],
        }
    yield {"type": "done", "message_id": gm_msg.id}


# ───────────────────────── итог боя ─────────────────────────


def resolve_combat(
    session: Session,
    adv: AdventureSession,
    outcome: dict,
    enemy_ids: Optional[list[int]] = None,
) -> Iterator[dict]:
    """Подвести итог завершившегося боя (поток событий), вернуться к повествованию.

    Бой ведёт ``web.simulation`` поверх ``engine.combat`` — здесь только LLM-рассказ
    об итоге и уборка сцены (снятие пинов с погибших противников).
    """
    mem_cfg = config.get_section(session, "memory")
    embed_model = config.get_section(session, "embedder")["model"]
    narrator_client = client_for(session, "narrator")

    kickoff = prompts.combat_outcome_kickoff(outcome)
    window_msgs = memory.window(adv, int(mem_cfg["window_messages"]))
    active = scene.collect_active(adv)
    context = prompts.build_context_block(
        running_summary=adv.running_summary,
        location=active["location"],
        npcs=active["npcs"],
        items=active["items"],
        lore_facts=[],
        episodic=[],
        enrichment="",
    )
    messages = narrator.build_messages(adv, context, window_msgs, kickoff=kickoff)

    gm_text = yield from _stream_and_collect(narrator_client, messages)
    gm_msg = _save_message(session, adv, role="gm", content=gm_text)

    if enemy_ids:
        survivor_names = set((outcome.get("survivors") or {}).get(_ENEMY_SIDE, []))
        cards = session.execute(select(Card).where(Card.id.in_(enemy_ids))).scalars().all()
        defeated_ids = [c.id for c in cards if c.name not in survivor_names]
        scene.unpin_cards(session, adv, defeated_ids)

    memory.record_turn(session, adv, gm_msg, model_name=embed_model)
    session.commit()

    yield {"type": "scene", "scene": scene.serialize_scene(adv)}
    yield {"type": "done", "message_id": gm_msg.id}


# ───────────────────────── вспомогательное ─────────────────────────


def _stream_and_collect(client, messages) -> Iterator[dict]:
    """Стримить ответ ГМ, отдавая дельты; вернуть собранный текст (generator return)."""
    chunks: list[str] = []
    try:
        for delta in narrator.stream(client, messages):
            chunks.append(delta)
            yield {"type": "delta", "text": delta}
    except LLMError as exc:
        note = f"\n\n[ГМ недоступен: {exc}]"
        chunks.append(note)
        yield {"type": "error", "error": str(exc)}
    return "".join(chunks)


def _save_message(
    session: Session,
    adv: AdventureSession,
    *,
    role: str,
    content: str,
    speaker_id: Optional[int] = None,
) -> AdventureMessage:
    msg = AdventureMessage(
        session_id=adv.id, role=role, content=content, speaker_character_id=speaker_id
    )
    adv.messages.append(msg)
    session.add(msg)
    session.flush()
    return msg
