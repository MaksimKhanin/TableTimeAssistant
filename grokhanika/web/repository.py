"""Доступ к данным админ-UI: выборка карточек по категориям и их создание.

Тонкий слой поверх SQLAlchemy-сессии. Витрина (фильтры/сортировки) описана
данными в :mod:`grokhanika.web.schema`; здесь — только их применение к запросу.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import (
    Ability,
    Armor,
    Card,
    Character,
    Creature,
    Instrument,
    Item,
    LoreEntry,
    Scroll,
    Skill,
    SpellBook,
    Weapon,
)
from ..enums import CardType
from . import schema
from .serialize import serialize_ability, serialize_card, serialize_character_for_party


def _index_card_safe(session: Session, card: Card) -> None:
    """Best-effort индексация карточки для RAG.

    Если модуль приключения/эмбеддер недоступны (нет sentence-transformers и пр.) —
    молча пропускаем: вектор досчитает ``scripts/reindex_embeddings``.
    """
    try:
        from ..adventure import retrieval

        retrieval.index_card(session, card, commit=True)
    except Exception:  # noqa: BLE001 - индексация не должна ломать основной поток
        session.rollback()

# конструкторы карточек по типу (имена полей формы == имена колонок ORM)
_MODELS: dict[str, type[Card]] = {
    CardType.CHARACTER.value: Character,
    CardType.CREATURE.value: Creature,
    CardType.WEAPON.value: Weapon,
    CardType.ARMOR.value: Armor,
    CardType.ITEM.value: Item,
    CardType.SPELLBOOK.value: SpellBook,
    CardType.SCROLL.value: Scroll,
    CardType.INSTRUMENT.value: Instrument,
    CardType.SKILL.value: Skill,
}

# поля-ссылки на другую карточку: имя поля → ожидаемая модель цели
_REFERENCE_FIELDS: dict[str, type[Card]] = {
    "equipped_weapon_id": Weapon,
    "equipped_armor_id": Armor,
    "grants_skill_id": Skill,
}


# ───────────────────────── сортировка карточек ─────────────────────────


def _sort_key(card: Card, sort: str):
    """Ключ сортировки. Числовые поля могут быть None → в конец."""
    if sort == "name":
        return (0, card.name.lower())
    if sort == "money":
        return (getattr(card, "money", 0) or 0,)
    if sort == "price":
        value = getattr(card, "price", None)
        return (value is None, value or 0)
    if sort == "hp":
        # у существа hp прямое поле, у персонажа — вычисляется (берём для сорта 0)
        value = getattr(card, "hp", None)
        return (value is None, value or 0)
    return (0, card.name.lower())


# ───────────────────────── выборка по категории ─────────────────────────


def list_category(
    session: Session,
    category_key: str,
    *,
    filter_value: str = "all",
    sort: str = "name",
    order: str = "asc",
) -> list[dict]:
    """Карточки (или способности) категории с учётом фильтра и сортировки."""
    category = schema.CATEGORIES_BY_KEY.get(category_key)
    if category is None:
        return []

    if category_key == "abilities":
        return _list_abilities(session, sort=sort, order=order)

    # какие типы карточек реально грузим (с учётом фильтра)
    types = list(category.card_types)
    # фильтр навыков (активные/пассивные) — не по типу карточки, отбираем после загрузки
    skill_passive_filter: Optional[bool] = None
    if filter_value and filter_value != "all":
        if category_key == "skills" and filter_value in ("active", "passive"):
            skill_passive_filter = filter_value == "passive"
        else:
            chosen = next((f for f in category.filters if f["value"] == filter_value), None)
            if chosen is not None:
                types = chosen.get("card_types", [filter_value])

    cards = (
        session.execute(select(Card).where(Card.card_type.in_(types)))
        .scalars()
        .all()
    )

    # категория «Герои» — только игровые персонажи; «NPC» — все существа + NPC
    if category_key == "heroes":
        cards = [c for c in cards if isinstance(c, Character) and c.is_player]
    elif category_key == "npc":
        cards = [c for c in cards if not (isinstance(c, Character) and c.is_player)]
    elif skill_passive_filter is not None:
        cards = [c for c in cards if isinstance(c, Skill) and c.is_passive == skill_passive_filter]

    reverse = order == "desc"
    cards.sort(key=lambda c: _sort_key(c, sort), reverse=reverse)
    return [serialize_card(c, full=True) for c in cards]


def _list_abilities(session: Session, *, sort: str, order: str) -> list[dict]:
    abilities = session.execute(select(Ability)).scalars().all()
    reverse = order == "desc"
    if sort == "chance":
        abilities.sort(key=lambda a: (a.chance is None, a.chance or 0.0), reverse=reverse)
    else:
        abilities.sort(key=lambda a: a.name.lower(), reverse=reverse)
    return [serialize_ability(a) for a in abilities]


def get_card(session: Session, card_id: int) -> Optional[dict]:
    card = session.get(Card, card_id)
    return serialize_card(card, full=True) if card is not None else None


# ───────────────────────── список существующих для choice-полей ─────────────────────────


def choices_for(session: Session, source: str) -> list[dict]:
    """Варианты для choice-поля формы (например, существующее оружие/броня)."""
    type_map = {
        "weapons": CardType.WEAPON.value,
        "armor": CardType.ARMOR.value,
        "skills": CardType.SKILL.value,
    }
    card_type = type_map.get(source)
    if card_type is None:
        return []
    cards = (
        session.execute(select(Card).where(Card.card_type == card_type).order_by(Card.name))
        .scalars()
        .all()
    )
    return [{"value": c.id, "label": c.name} for c in cards]


# ───────────────────────── создание карточки ─────────────────────────


def get_party(session: Session) -> list[dict]:
    """Все игровые персонажи для экрана состояния группы."""
    chars = (
        session.execute(select(Character).where(Character.is_player == True))
        .scalars()
        .all()
    )
    chars.sort(key=lambda c: c.name.lower())
    return [serialize_character_for_party(c) for c in chars]


def equip_character(session: Session, char_id: int, slot: str, card_id: Optional[int]) -> dict:
    """Экипировать или снять оружие/броню у персонажа.
    card_id=None → снять в инвентарь.
    card_id указан → взять только из собственного инвентаря персонажа;
    старый экипированный предмет автоматически уходит в инвентарь.
    """
    char = session.get(Character, char_id)
    if char is None:
        raise CreateError({"__form__": "Персонаж не найден"})
    if slot not in ("weapon", "armor"):
        raise CreateError({"slot": f"Неизвестный слот: {slot!r}"})

    old_item = char.equipped_weapon if slot == "weapon" else char.equipped_armor

    if card_id is None:
        # Снять → вернуть в инвентарь
        if old_item is not None:
            if old_item not in char.inventory:
                char.inventory.append(old_item)
            if slot == "weapon":
                char.equipped_weapon_id = None
            else:
                char.equipped_armor_id = None
    else:
        # Экипировать: только из собственного инвентаря
        inv_card = next((it for it in char.inventory if it.id == card_id), None)
        if inv_card is None:
            raise CreateError({"slot": "Предмет не найден в инвентаре персонажа"})
        if slot == "weapon" and not isinstance(inv_card, Weapon):
            raise CreateError({"slot": "В слот оружия можно экипировать только оружие"})
        if slot == "armor" and not isinstance(inv_card, Armor):
            raise CreateError({"slot": "В слот доспеха можно экипировать только броню"})
        char.inventory.remove(inv_card)
        if old_item is not None and old_item not in char.inventory:
            char.inventory.append(old_item)
        if slot == "weapon":
            char.equipped_weapon_id = card_id
        else:
            char.equipped_armor_id = card_id

    session.commit()
    session.refresh(char)
    return serialize_character_for_party(char)


def list_equipment(session: Session) -> dict:
    """Все оружие и броня в системе — для выбора экипировки."""
    weapons = (
        session.execute(select(Weapon).order_by(Weapon.name)).scalars().all()
    )
    armor = (
        session.execute(select(Armor).order_by(Armor.name)).scalars().all()
    )
    return {
        "weapons": [{"id": w.id, "name": w.name, "damage_dice": w.damage_dice,
                     "description": w.description or "", "price": w.price} for w in weapons],
        "armor": [{"id": a.id, "name": a.name, "phys_def_bonus": a.phys_def_bonus,
                   "description": a.description or "", "price": a.price} for a in armor],
    }


class CreateError(Exception):
    """Ошибки валидации формы. ``errors`` — карта {поле: сообщение}."""

    def __init__(self, errors: dict) -> None:
        super().__init__("ошибка валидации формы")
        self.errors = errors


class UpdateError(Exception):
    """Ошибки при обновлении карточки. ``errors`` — карта {поле: сообщение}."""

    def __init__(self, errors: dict) -> None:
        super().__init__("ошибка обновления карточки")
        self.errors = errors


def delete_card(session: Session, card_id: int) -> bool:
    """Удалить карточку по id. Возвращает True если удалена, False если не найдена."""
    card = session.get(Card, card_id)
    if card is None:
        return False
    session.delete(card)
    session.commit()
    return True


def create_card(session: Session, card_type: str, payload: dict) -> dict:
    """Создать карточку из данных формы. Бросает :class:`CreateError`."""
    cleaned, errors = schema.validate_payload(card_type, payload)
    if errors:
        raise CreateError(errors)

    model = _MODELS.get(card_type)
    if model is None:  # pragma: no cover - validate_payload уже отсеял
        raise CreateError({"__form__": f"Неизвестный тип карточки: {card_type!r}"})

    # проверяем ссылки на другие карточки (оружие/броня персонажа)
    for fld, ref_model in _REFERENCE_FIELDS.items():
        if fld in cleaned:
            ref = session.get(ref_model, cleaned[fld])
            if ref is None:
                raise CreateError({fld: "Карточка не найдена"})

    card = model(**cleaned)
    session.add(card)
    session.commit()
    _index_card_safe(session, card)  # сделать карточку доступной семантическому поиску
    return serialize_card(card, full=True)


# ───────────────────────── лор-записи (CRUD для приключения) ─────────────────────────

_LORE_CATEGORIES = ("location", "faction", "history", "custom")


def list_lore(session: Session, *, category: Optional[str] = None) -> list[dict]:
    """Список лор-записей, опционально по категории."""
    stmt = select(LoreEntry)
    if category and category != "all":
        stmt = stmt.where(LoreEntry.category == category)
    entries = session.execute(stmt.order_by(LoreEntry.name)).scalars().all()
    return [serialize_card(e, full=True) for e in entries]


def _clean_lore(payload: dict) -> dict:
    name = (payload.get("name") or "").strip()
    if not name:
        raise CreateError({"name": "Укажите название"})
    category = (payload.get("category") or "custom").strip()
    if category not in _LORE_CATEGORIES:
        category = "custom"
    return {
        "name": name,
        "description": (payload.get("description") or "").strip(),
        "category": category,
    }


def create_lore(session: Session, payload: dict) -> dict:
    """Создать лор-запись и проиндексировать её."""
    entry = LoreEntry(**_clean_lore(payload))
    session.add(entry)
    session.commit()
    _index_card_safe(session, entry)
    return serialize_card(entry, full=True)


def update_lore(session: Session, lore_id: int, payload: dict) -> Optional[dict]:
    """Отредактировать лор-запись и переиндексировать её. None — если не найдена."""
    entry = session.get(LoreEntry, lore_id)
    if entry is None:
        return None
    cleaned = _clean_lore(payload)
    entry.name = cleaned["name"]
    entry.description = cleaned["description"]
    entry.category = cleaned["category"]
    session.commit()
    _index_card_safe(session, entry)
    return serialize_card(entry, full=True)


def delete_lore(session: Session, lore_id: int) -> bool:
    """Удалить лор-запись и её эмбеддинг. True — если удалили."""
    entry = session.get(LoreEntry, lore_id)
    if entry is None:
        return False
    try:
        from ..adventure import retrieval

        retrieval.remove_entity(session, retrieval.ENTITY_LORE, lore_id, commit=False)
    except Exception:  # noqa: BLE001
        pass
    session.delete(entry)
    session.commit()
    return True


def update_card(session: Session, card_id: int, card_type: str, payload: dict) -> Optional[dict]:
    """Обновить существующую карточку. Бросает :class:`UpdateError` при ошибках."""
    card = session.get(Card, card_id)
    if card is None:
        return None

    if card.card_type != card_type:
        raise UpdateError({"__form__": "Нельзя изменить тип карточки"})

    cleaned, errors = schema.validate_payload(card_type, payload)
    if errors:
        raise UpdateError(errors)

    for fld, ref_model in _REFERENCE_FIELDS.items():
        if fld in cleaned:
            ref = session.get(ref_model, cleaned[fld])
            if ref is None:
                raise UpdateError({fld: "Карточка не найдена"})

    for k, v in cleaned.items():
        setattr(card, k, v)

    session.commit()
    _index_card_safe(session, card)  # переиндексировать после правки (для RAG)
    return serialize_card(card, full=True)
