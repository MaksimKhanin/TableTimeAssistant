"""Модель действия хода (команда).

Действие — это *намерение* участника на свой ход, выраженное данными. Менеджер
боя (``engine.encounter``) валидирует его и вызывает соответствующий метод
``Combat``. Модель экономики — одно действие за ход (§11: зелье «тратит ход»;
групповые механики тратят ход инициатора).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ActionKind(str, Enum):
    ATTACK_PHYSICAL = "attack_physical"
    CAST_SPELL = "cast_spell"
    ATTACK_MENTAL = "attack_mental"
    USE_POTION = "use_potion"
    FLEE = "flee"
    INTIMIDATE = "intimidate"
    NEGOTIATE = "negotiate"
    PASS = "pass"


@dataclass
class Action:
    """Намерение участника на ход. ``target_uid`` адресует ``Combatant.uid``."""

    kind: ActionKind
    target_uid: Optional[int] = None
    enemy_side: Optional[str] = None
    carrier_card_id: Optional[int] = None
    item_name: Optional[str] = None
    effect: Optional[object] = None  # RuntimeEffect для ментальной атаки

    # ── фабрики для краткости ──

    @classmethod
    def attack(cls, target_uid: int) -> "Action":
        return cls(ActionKind.ATTACK_PHYSICAL, target_uid=target_uid)

    @classmethod
    def cast(cls, target_uid: int, carrier_card_id: int) -> "Action":
        return cls(ActionKind.CAST_SPELL, target_uid=target_uid, carrier_card_id=carrier_card_id)

    @classmethod
    def mental(cls, target_uid: int, effect: object = None) -> "Action":
        return cls(ActionKind.ATTACK_MENTAL, target_uid=target_uid, effect=effect)

    @classmethod
    def potion(cls, item_name: Optional[str] = None) -> "Action":
        return cls(ActionKind.USE_POTION, item_name=item_name)

    @classmethod
    def flee(cls) -> "Action":
        return cls(ActionKind.FLEE)

    @classmethod
    def intimidate(cls, enemy_side: str) -> "Action":
        return cls(ActionKind.INTIMIDATE, enemy_side=enemy_side)

    @classmethod
    def negotiate(cls, enemy_side: str) -> "Action":
        return cls(ActionKind.NEGOTIATE, enemy_side=enemy_side)

    @classmethod
    def do_nothing(cls) -> "Action":
        return cls(ActionKind.PASS)
