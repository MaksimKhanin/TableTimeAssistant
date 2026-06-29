"""Валидация распределения характеристик (манифест §2).

PC: база 5 по каждой из 4 характеристик, +10 очков на распределение, снижать
можно до 1 (возвращает очки), капы нет. NPC не валидируется (§0).
"""
from __future__ import annotations

from dataclasses import dataclass

BASE_STAT = 5
DISTRIBUTION_POINTS = 10
MIN_STAT = 1


class PointBuyError(ValueError):
    """Распределение характеристик нарушает правила пойнт-бая."""


@dataclass
class PointBuyReport:
    spent: int
    remaining: int
    valid: bool


def points_spent(strength: int, dexterity: int, wisdom: int, charisma: int) -> int:
    """Сколько очков потрачено (снижение ниже базы возвращает очки)."""
    return sum(s - BASE_STAT for s in (strength, dexterity, wisdom, charisma))


def validate_point_buy(
    strength: int, dexterity: int, wisdom: int, charisma: int
) -> PointBuyReport:
    """Проверить распределение очков игрового персонажа. Бросает PointBuyError."""
    stats = {
        "strength": strength,
        "dexterity": dexterity,
        "wisdom": wisdom,
        "charisma": charisma,
    }
    for name, value in stats.items():
        if value < MIN_STAT:
            raise PointBuyError(f"{name}={value} ниже минимума {MIN_STAT}")

    spent = points_spent(strength, dexterity, wisdom, charisma)
    if spent > DISTRIBUTION_POINTS:
        raise PointBuyError(
            f"потрачено {spent} очков из {DISTRIBUTION_POINTS} — превышение"
        )
    return PointBuyReport(
        spent=spent, remaining=DISTRIBUTION_POINTS - spent, valid=True
    )
