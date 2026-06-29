"""Кубики и броски (манифест §7).

Кубики: d4, d6, d8, d10, d12, d20.
Натуральная 20 → критический удар (двойной урон по кубикам).
Натуральная 1  → критический провал (автопромах).

Весь рандом проходит через ``random.Random``, который можно передать снаружи —
это делает бой детерминированным в тестах.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass

ALLOWED_SIDES = {4, 6, 8, 10, 12, 20}
_DICE_RE = re.compile(r"^\s*(\d+)\s*[dD]\s*(\d+)\s*$")


@dataclass(frozen=True)
class Dice:
    """Кубиковая нотация вида ``NdM`` (например, ``2d4``)."""

    count: int
    sides: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError(f"count must be >= 1, got {self.count}")
        if self.sides not in ALLOWED_SIDES:
            raise ValueError(f"unsupported die d{self.sides}; allowed: {sorted(ALLOWED_SIDES)}")

    @classmethod
    def parse(cls, notation: str) -> "Dice":
        m = _DICE_RE.match(notation)
        if not m:
            raise ValueError(f"invalid dice notation: {notation!r}")
        return cls(int(m.group(1)), int(m.group(2)))

    @property
    def notation(self) -> str:
        return f"{self.count}d{self.sides}"

    @property
    def maximum(self) -> int:
        return self.count * self.sides

    @property
    def minimum(self) -> int:
        return self.count

    def roll(self, rng: random.Random, *, crit: bool = False) -> int:
        """Бросить кубики. При ``crit`` число кубиков удваивается (двойной урон)."""
        count = self.count * 2 if crit else self.count
        return sum(rng.randint(1, self.sides) for _ in range(count))


def roll_d20(rng: random.Random) -> int:
    """Натуральный бросок d20 (1..20), без модификаторов."""
    return rng.randint(1, 20)


def is_crit(natural: int) -> bool:
    return natural == 20


def is_fumble(natural: int) -> bool:
    return natural == 1
