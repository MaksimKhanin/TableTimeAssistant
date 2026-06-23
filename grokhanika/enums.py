"""Перечисления игровой системы «Гроханика».

Используем строковые Enum (``str, Enum``) — значения читаемы и напрямую
сохраняются в БД без дополнительных конвертеров.
"""
from __future__ import annotations

from enum import Enum


class CardType(str, Enum):
    """Тип карточки (дискриминатор в таблице ``cards``)."""

    CHARACTER = "character"
    CREATURE = "creature"
    WEAPON = "weapon"
    ARMOR = "armor"
    ITEM = "item"
    SPELLBOOK = "spellbook"
    SCROLL = "scroll"
    INSTRUMENT = "instrument"


class Stat(str, Enum):
    """Четыре базовые характеристики персонажа."""

    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    WISDOM = "wisdom"
    CHARISMA = "charisma"


class EffectTargetType(str, Enum):
    """Эффект меняет либо характеристику (stat), либо атрибут (attr)."""

    STAT = "stat"
    ATTR = "attr"


class EffectTarget(str, Enum):
    """На что направлен эффект.

    ``ALL_D20_ROLLS`` — любой бросок d20 (атаки, спасброски, защита, побег).
    ``ALL_ATTACK_ROLLS`` — только броски атаки (физ./маг./мент.); используется
    для дебаффа морали (манифест §12). В исходном списке §5 этой цели нет —
    это намеренное расширение, чтобы корректно реализовать мораль, не задевая
    спасброски и защиту.
    """

    # цели-характеристики (target_type == STAT)
    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    WISDOM = "wisdom"
    CHARISMA = "charisma"
    # цели-атрибуты (target_type == ATTR)
    HP = "hp"
    PHYS_DEFENSE = "phys_defense"
    MAG_DEFENSE = "mag_defense"
    MENTAL_DEFENSE = "mental_defense"
    PHYS_DAMAGE = "phys_damage"
    ALL_D20_ROLLS = "all_d20_rolls"
    ALL_ATTACK_ROLLS = "all_attack_rolls"


class SourceType(str, Enum):
    """Источник эффекта."""

    WEAPON = "weapon"
    ARMOR = "armor"
    SPELL = "spell"
    ITEM = "item"
    MORALE = "morale"


class ActivationSource(str, Enum):
    """Условие, при котором эффект активен."""

    EQUIPPED_WEAPON = "equipped_weapon"
    EQUIPPED_ARMOR = "equipped_armor"
    IN_INVENTORY = "in_inventory"
    # активен, только если экипировано дальнобойное оружие (лук/арбалет)
    IN_INVENTORY_RANGED = "in_inventory+ranged"


class AttackType(str, Enum):
    """Виды атак."""

    PHYSICAL = "physical"
    MAGICAL = "magical"
    MENTAL = "mental"


class HPState(str, Enum):
    """Состояние персонажа по HP (манифест §11)."""

    ACTIVE = "active"  # HP > 0
    DYING = "dying"    # HP == 0, без сознания, но не мёртв


class AbilityTrigger(str, Enum):
    """Когда срабатывает способность (data-driven, манифест: уникальные предметы)."""

    ACTIVE = "active"             # активируется вручную, тратит действие
    ON_ATTACK = "on_attack"       # когда носитель атакует
    ON_HIT = "on_hit"             # при успешном попадании
    ON_KILL = "on_kill"           # когда носитель убил цель
    ON_DAMAGED = "on_damaged"     # когда носитель получил урон
    ON_TURN_START = "on_turn_start"
    ON_COMBAT_START = "on_combat_start"


class ActionType(str, Enum):
    """Атомарные действия, из которых собираются способности."""

    DAMAGE = "damage"             # нанести урон (кубики)
    HEAL = "heal"                 # вылечить
    APPLY_EFFECT = "apply_effect" # навесить эффект
    SUMMON = "summon"             # призвать существо
    INSTAKILL = "instakill"       # мгновенное убийство (по шансу)
    APPLY_MORALE = "apply_morale" # дебафф морали на сторону
