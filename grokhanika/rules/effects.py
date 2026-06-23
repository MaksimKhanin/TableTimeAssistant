"""Рантайм-эффекты и их агрегация (манифест §5).

ORM-``Effect`` — шаблон в БД, привязанный к карточке. В бою мы работаем с
``RuntimeEffect`` — снимком с «живой» длительностью (декремент по раундам).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from ..enums import EffectTarget, EffectTargetType


@dataclass
class RuntimeEffect:
    """Активный эффект на конкретном участнике боя."""

    target_type: str
    target: str
    modifier: int = 0
    duration: int = 0  # 0 = постоянный (снимается только с источником)
    source_type: str = "item"
    source_id: Optional[int] = None
    activation_source: Optional[str] = None
    is_stackable: bool = True
    visible_to_player: bool = False
    description: str = ""

    @classmethod
    def from_orm(cls, effect) -> "RuntimeEffect":
        return cls(
            target_type=effect.target_type,
            target=effect.target,
            modifier=effect.modifier,
            duration=effect.duration,
            source_type=effect.source_type,
            source_id=effect.owner_card_id,
            activation_source=effect.activation_source,
            is_stackable=effect.is_stackable,
            visible_to_player=effect.visible_to_player,
            description=effect.description,
        )


def _norm(value) -> str:
    return value.value if hasattr(value, "value") else value


def sum_for(effects: Iterable[RuntimeEffect], target_type, target) -> int:
    """Сумма модификаторов эффектов с заданными типом и целью."""
    tt, tg = _norm(target_type), _norm(target)
    return sum(e.modifier for e in effects if e.target_type == tt and e.target == tg)


def stat_modifier(effects: Iterable[RuntimeEffect], stat) -> int:
    return sum_for(effects, EffectTargetType.STAT, stat)


def attr_modifier(effects: Iterable[RuntimeEffect], attr) -> int:
    return sum_for(effects, EffectTargetType.ATTR, attr)


def roll_modifier(effects: Iterable[RuntimeEffect], *, attack: bool) -> int:
    """Глобальный модификатор к броску d20 в момент броска.

    Всегда учитывает ``ALL_D20_ROLLS`` (талисман удачи), а для бросков атаки
    дополнительно — ``ALL_ATTACK_ROLLS`` (дебафф морали).
    """
    total = attr_modifier(effects, EffectTarget.ALL_D20_ROLLS)
    if attack:
        total += attr_modifier(effects, EffectTarget.ALL_ATTACK_ROLLS)
    return total


def add_effect(active: list[RuntimeEffect], effect: RuntimeEffect) -> None:
    """Добавить эффект с учётом стэкуемости (манифест §5).

    ``is_stackable=False`` → повторное применение из того же источника на ту же
    цель обновляет длительность, а не суммируется.
    """
    if not effect.is_stackable:
        for existing in active:
            if (
                existing.source_id == effect.source_id
                and existing.target == effect.target
                and existing.target_type == effect.target_type
                and not existing.is_stackable
            ):
                existing.duration = effect.duration
                return
    active.append(effect)


def tick_round(active: list[RuntimeEffect]) -> list[RuntimeEffect]:
    """Декремент длительностей в конце раунда; снять истёкшие (§5).

    Возвращает список снятых эффектов. ``duration == 0`` — постоянные, не тикают.
    """
    removed: list[RuntimeEffect] = []
    for effect in list(active):
        if effect.duration > 0:
            effect.duration -= 1
            if effect.duration == 0:
                active.remove(effect)
                removed.append(effect)
    return removed
