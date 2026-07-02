"""Состояние сцены приключения: закреплённые карточки и текущая локация.

Сцена — это структурное состояние вне транскрипта (в БД): какие NPC/предметы
сейчас «в кадре» и где находится партия. Это и показывается игроку в панели
сцены, и подставляется в промт ГМ. При уходе из локации неигровые акторы
деактивируются (а не удаляются — историю сохраняем).
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy.orm import Session

from ..db.models import AdventureSession, Card, ScenePin
from ..web.serialize import serialize_card

KIND_NPC = "npc"
KIND_LOCATION = "location"
KIND_ITEM = "item"


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


def pin_card(session: Session, adv: AdventureSession, card: Card, kind: str) -> ScenePin:
    """Закрепить карточку в сцене (создать или реактивировать пин)."""
    existing = next((p for p in adv.pins if p.card_id == card.id), None)
    if existing is not None:
        existing.active = True
        existing.kind = kind
        session.flush()
        return existing
    pin = ScenePin(session_id=adv.id, card_id=card.id, kind=kind, active=True)
    adv.pins.append(pin)
    session.add(pin)
    session.flush()
    return pin


def set_location(session: Session, adv: AdventureSession, card: Card) -> None:
    """Сделать карточку текущей локацией (деактивирует прежнюю локацию)."""
    for pin in _active_pins(adv, KIND_LOCATION):
        if pin.card_id != card.id:
            pin.active = False
    adv.current_location_card_id = card.id
    pin_card(session, adv, card, KIND_LOCATION)


def collect_active(adv: AdventureSession) -> dict:
    """ORM-объекты активной сцены, сгруппированные по виду (для промта)."""
    location = next((p.card for p in _active_pins(adv, KIND_LOCATION)), None)
    npcs = [p.card for p in _active_pins(adv, KIND_NPC)]
    items = [p.card for p in _active_pins(adv, KIND_ITEM)]
    return {"location": location, "npcs": npcs, "items": items}


def serialize_scene(adv: AdventureSession) -> dict:
    """Сцена для фронтенда (карточки с артом)."""
    active = collect_active(adv)
    return {
        "location": serialize_card(active["location"]) if active["location"] else None,
        "npcs": [serialize_card(c) for c in active["npcs"]],
        "items": [serialize_card(c) for c in active["items"]],
    }
