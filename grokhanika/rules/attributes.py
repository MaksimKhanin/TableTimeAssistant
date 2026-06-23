"""Формулы вычисляемых атрибутов (манифест §3).

Порядок пересчёта:
  1. базовые характеристики
  2. + эффекты на stat
  3. → формулы атрибутов
  4. + эффекты на attr

Функции чистые: принимают уже эффективные характеристики и список активных
эффектов, ничего не мутируют.
"""
from __future__ import annotations

from typing import Iterable

from ..enums import EffectTarget, Stat
from .effects import RuntimeEffect, attr_modifier, stat_modifier


def effective_stat(base: int, effects: Iterable[RuntimeEffect], stat: Stat) -> int:
    """Характеристика с учётом всех stat-эффектов (шаг 2)."""
    return base + stat_modifier(effects, stat)


# ── атрибуты персонажа (вычисляются из характеристик) ──

def character_max_hp(str_eff: int, effects: Iterable[RuntimeEffect]) -> int:
    return 15 + str_eff + attr_modifier(effects, EffectTarget.HP)


def character_phys_defense(
    dex_eff: int, armor_phys_def_bonus: int, effects: Iterable[RuntimeEffect]
) -> int:
    # 5 + DEX_eff//2 + armor.phys_def_bonus + эффекты на phys_defense (напр. щит)
    return (
        5
        + dex_eff // 2
        + armor_phys_def_bonus
        + attr_modifier(effects, EffectTarget.PHYS_DEFENSE)
    )


def character_mag_defense(wis_eff: int, effects: Iterable[RuntimeEffect]) -> int:
    # без базы 5 (манифест §3): WIS_eff//2
    return wis_eff // 2 + attr_modifier(effects, EffectTarget.MAG_DEFENSE)


def character_mental_defense(cha_eff: int, effects: Iterable[RuntimeEffect]) -> int:
    return 5 + cha_eff // 2 + attr_modifier(effects, EffectTarget.MENTAL_DEFENSE)


# ── атрибуты существа (защиты заданы напрямую, манифест §13) ──

def creature_max_hp(base_hp: int, effects: Iterable[RuntimeEffect]) -> int:
    return base_hp + attr_modifier(effects, EffectTarget.HP)


def creature_defense(
    base: int, effects: Iterable[RuntimeEffect], target: EffectTarget
) -> int:
    return base + attr_modifier(effects, target)


# ── общее для бросков и урона ──

def attack_bonus(stat_eff: int) -> int:
    """Прибавка к броску атаки: stat_eff // 2 (физ→DEX, маг→WIS, мент→CHA)."""
    return stat_eff // 2


def damage_bonus(str_eff: int, effects: Iterable[RuntimeEffect]) -> int:
    """Бонус к физ. урону: STR_eff//2 + эффекты на phys_damage (напр. маг. стрелы)."""
    return str_eff // 2 + attr_modifier(effects, EffectTarget.PHYS_DAMAGE)
