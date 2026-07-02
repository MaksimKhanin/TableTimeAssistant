"""Состояние сцены приключения: закреплённые NPC и текущая локация.

Сцена — это структурное состояние вне транскрипта (в БД): какие NPC сейчас
«в кадре», сколько их и где находится партия. Это и показывается игроку в
панели сцены, и подставляется в промт ГМ.

Локация — свободный текст (имя + описание), не карточка каталога: её решает
интент-анализатор (детерминированно), а не RAG-поиск по лору (см.
``adventure.intent``). NPC остаются карточками каталога (нужны их арт/статы
для боя), но с явным количеством (``count``), чтобы «два стражника» в
повествовании были именно двумя закреплёнными стражниками, а не одним.

При уходе из локации неигровые акторы деактивируются (а не удаляются —
историю сохраняем).
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy.orm import Session

from ..db.models import AdventureSession, Card, ScenePin
from ..web.serialize import serialize_card

KIND_NPC = "npc"


def _active_pins(adv: AdventureSession, kind: Optional[str] = None) -> list[ScenePin]:
    pins = [p for p in adv.pins if p.active]
    if kind is not None:
        pins = [p for p in pins if p.kind == kind]
    return pins


def clear_npcs(session: Session, adv: AdventureSession) -> None:
    """Деактивировать всех NPC сцены (уход из локации/смена места)."""
    for pin in _active_pins(adv, KIND_NPC):
        pin.active = False
    session.flush()


def unpin_cards(session: Session, adv: AdventureSession, card_ids: Iterable[int]) -> None:
    """Снять пины конкретных карточек (например, погибших в бою противников)."""
    ids = set(card_ids)
    if not ids:
        return
    for pin in adv.pins:
        if pin.active and pin.card_id in ids:
            pin.active = False
    session.flush()


def pin_card(session: Session, adv: AdventureSession, card: Card, kind: str, count: int = 1) -> ScenePin:
    """Закрепить карточку в сцене с заданным количеством (создать или реактивировать пин)."""
    count = max(1, int(count))
    existing = next((p for p in adv.pins if p.card_id == card.id), None)
    if existing is not None:
        existing.active = True
        existing.kind = kind
        existing.count = count
        session.flush()
        return existing
    pin = ScenePin(session_id=adv.id, card_id=card.id, kind=kind, count=count, active=True)
    adv.pins.append(pin)
    session.add(pin)
    session.flush()
    return pin


def set_location_text(session: Session, adv: AdventureSession, name: str, description: str = "") -> None:
    """Задать текущую локацию свободным текстом (без привязки к карточкам каталога)."""
    adv.current_location_name = name.strip()
    adv.current_location_description = description.strip()
    session.flush()


def collect_active(adv: AdventureSession) -> dict:
    """Активная сцена для промта: локация (текст) и NPC (карточка + количество)."""
    npcs = [{"card": p.card, "count": p.count} for p in _active_pins(adv, KIND_NPC)]
    location = None
    if adv.current_location_name:
        location = {"name": adv.current_location_name, "description": adv.current_location_description}
    return {"location": location, "npcs": npcs}


def serialize_scene(adv: AdventureSession) -> dict:
    """Сцена для фронтенда (локация текстом, NPC — карточки с артом и количеством)."""
    active = collect_active(adv)
    npcs = []
    for entry in active["npcs"]:
        data = serialize_card(entry["card"])
        data["count"] = entry["count"]
        npcs.append(data)
    return {"location": active["location"], "npcs": npcs}
