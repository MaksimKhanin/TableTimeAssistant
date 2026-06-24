"""Сериализация ORM-карточек в JSON-словари для фронтенда.

Карточка отдаётся с тремя слоями данных:

* **общие поля** (id, тип, имя, описание, арт);
* **поля типа** (урон оружия, HP существа, …) — для подробной карточки;
* **вычисленный стат-блок** (HP, защиты, бонусы атак) для персонажей и существ —
  считается тем же движком, что и в бою (``Combatant``), так что админ видит те
  же числа, что игрок.
"""
from __future__ import annotations

import os
from typing import Optional

from flask import url_for

from ..db.models import (
    Ability,
    Armor,
    Card,
    Character,
    Creature,
    Instrument,
    Item,
    Scroll,
    Skill,
    SpellBook,
    Weapon,
)
from ..engine.combatant import Combatant
from ..enums import CardType

# где лежит арт карточек (имя файла берётся из Card.image_id)
_IMAGES_SUBDIR = os.path.join("images", "cards")


# ───────────────────────── изображение ─────────────────────────


def _image_url(card: Card) -> Optional[str]:
    """URL арта карточки или ``None`` (тогда фронт рисует заглушку по типу)."""
    if not card.image_id:
        return None
    static_root = os.path.join(os.path.dirname(__file__), "static")
    path = os.path.join(static_root, _IMAGES_SUBDIR, card.image_id)
    if not os.path.isfile(path):
        return None
    return url_for("static", filename=f"{_IMAGES_SUBDIR}/{card.image_id}")


# ───────────────────────── стат-блок (через движок) ─────────────────────────


def _stat_block(card: Card) -> Optional[dict]:
    """Вычисленные боевые атрибуты персонажа/существа (как в бою)."""
    if not isinstance(card, (Character, Creature)):
        return None
    try:
        c = Combatant(card, side="preview")
    except Exception:  # pragma: no cover - не валим витрину из-за кривой карточки
        return None
    return {
        "hp": c.max_hp,
        "phys_defense": c.phys_defense,
        "mag_defense": c.mag_defense,
        "mental_defense": c.mental_defense,
        "phys_attack_bonus": c.phys_attack_bonus,
        "mag_attack_bonus": c.mag_attack_bonus,
        "mental_attack_bonus": c.mental_attack_bonus,
        "phys_damage": c.phys_damage_dice,
    }


# ───────────────────────── поля по типу карточки ─────────────────────────


def _type_fields(card: Card) -> dict:
    if isinstance(card, Character):
        return {
            "is_player": card.is_player,
            "is_sentient": card.is_sentient,
            "strength": card.base_strength,
            "dexterity": card.base_dexterity,
            "wisdom": card.base_wisdom,
            "charisma": card.base_charisma,
            "money": card.money,
            "weapon": card.equipped_weapon.name if card.equipped_weapon else None,
            "armor": card.equipped_armor.name if card.equipped_armor else None,
            "inventory": [it.name for it in card.inventory],
            "skills": [s.name for s in card.skills],
        }
    if isinstance(card, Creature):
        return {
            "is_sentient": card.is_sentient,
            "hp": card.hp,
            "dexterity": card.dexterity,
            "phys_defense": card.phys_defense,
            "mag_defense": card.mag_defense,
            "mental_defense": card.mental_defense,
            "phys_damage_dice": card.phys_damage_dice,
            "strength": card.strength,
            "charisma": card.charisma,
            "wisdom": card.wisdom,
        }
    if isinstance(card, Weapon):
        return {
            "damage_dice": card.damage_dice,
            "str_requirement": card.str_requirement,
            "dex_requirement": card.dex_requirement,
            "is_ranged": card.is_ranged,
            "price": card.price,
        }
    if isinstance(card, Armor):
        return {
            "phys_def_bonus": card.phys_def_bonus,
            "str_requirement": card.str_requirement,
            "dex_requirement": card.dex_requirement,
            "price": card.price,
        }
    if isinstance(card, Item):
        return {
            "is_consumable": card.is_consumable,
            "heal_dice": card.heal_dice,
            "price": card.price,
        }
    if isinstance(card, (SpellBook, Scroll)):
        return {
            "spell_name": card.spell_name,
            "damage_dice": card.damage_dice,
            "heal_dice": card.heal_dice,
            "difficulty": card.difficulty,
            "attack_stat": card.attack_stat,
            "is_consumable": card.is_consumable,
            "price": card.price,
        }
    if isinstance(card, Skill):
        return {
            "is_passive": card.is_passive,
            "spell_name": card.spell_name or None,
            "damage_dice": card.damage_dice,
            "heal_dice": card.heal_dice,
            "difficulty": card.difficulty,
            "attack_stat": card.attack_stat if card.damage_dice else None,
            "price": card.price,
            "non_sellable": True,  # навык нельзя продать
            "in_inventory": False,  # навык не занимает слот инвентаря
        }
    if isinstance(card, Instrument):
        return {"price": card.price}
    return {}


# ───────────────────────── публичные сериализаторы ─────────────────────────

# человекочитаемые имена типов
TYPE_LABELS = {
    CardType.CHARACTER.value: "Персонаж",
    CardType.CREATURE.value: "Существо",
    CardType.WEAPON.value: "Оружие",
    CardType.ARMOR.value: "Броня",
    CardType.ITEM.value: "Предмет",
    CardType.SPELLBOOK.value: "Том магии",
    CardType.SCROLL.value: "Свиток",
    CardType.INSTRUMENT.value: "Инструмент",
    CardType.SKILL.value: "Навык",
}


def serialize_card(card: Card, *, full: bool = True) -> dict:
    """Карточка → словарь. ``full`` добавляет поля типа и стат-блок."""
    data = {
        "id": card.id,
        "card_type": card.card_type,
        "type_label": TYPE_LABELS.get(card.card_type, card.card_type),
        "name": card.name,
        "description": card.description or "",
        "image_id": card.image_id,
        "image_url": _image_url(card),
        "is_unique": card.is_unique,
        "abilities": [a.name for a in card.abilities],
    }
    if full:
        data["fields"] = _type_fields(card)
        stats = _stat_block(card)
        if stats is not None:
            data["stats"] = stats
    return data


def _actions_summary(ability: Ability) -> str:
    """Короткое описание действий способности для витрины."""
    parts = []
    for act in ability.actions or []:
        t = act.get("type", "?")
        if t == "summon":
            parts.append(f"призыв ×{act.get('count', 1)}")
        elif t == "instakill":
            parts.append("мгновенное убийство")
        elif t in ("buff_allies", "debuff_enemies"):
            parts.append("бафф союзников" if t == "buff_allies" else "дебафф врагов")
        else:
            parts.append(t)
    return ", ".join(parts)


def serialize_ability(ability: Ability) -> dict:
    """Способность → словарь (для категории «Способности»)."""
    return {
        "id": ability.id,
        "name": ability.name,
        "description": ability.description or "",
        "trigger": ability.trigger,
        "chance": ability.chance,
        "once_per_combat": ability.once_per_combat,
        "owner": ability.owner.name if ability.owner else None,
        "owner_type": ability.owner.card_type if ability.owner else None,
        "actions_summary": _actions_summary(ability),
    }
