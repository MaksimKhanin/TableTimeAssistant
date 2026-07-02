"""Загрузка каталога карточек из YAML (``grokhanika/data/catalog/``).

Каждый файл — один тип карточки (см. ``_MODEL_FOR_FILE``), ключ верхнего
уровня — стабильный id карточки (используется тестами через
``session.info["catalog"]``, а также перекрёстными ссылками внутри YAML).

Загрузка идёт в два прохода, потому что ссылки между карточками
(``equipped_weapon``, ``grants_skill`` и т.п.) не зависят от порядка файлов
или записей — как и раньше в ``db/seed.py``, где такие ссылки нередко
проставлялись постфактум (например ``tome_arrows.teaches_skill = ...``):

1. первый проход строит каждую карточку по скалярным полям + вложенным
   ``effects``/``abilities`` (owned children, без ссылок на другие карточки);
2. второй проход резолвит отложенные поля-ссылки через словарь ``id -> карточка``.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .models import (
    Ability,
    Armor,
    Card,
    Character,
    Creature,
    Effect,
    Instrument,
    Item,
    LoreEntry,
    Scroll,
    Skill,
    SpellBook,
    Weapon,
)

CATALOG_DIR = Path(__file__).resolve().parent.parent / "data" / "catalog"
IMAGES_DIR = Path(__file__).resolve().parent.parent / "data" / "images"
STATIC_CARD_IMAGES_DIR = (
    Path(__file__).resolve().parent.parent / "web" / "static" / "images" / "cards"
)

# файл каталога -> ORM-класс карточки этого типа
_MODEL_FOR_FILE: dict[str, type[Card]] = {
    "weapons.yaml": Weapon,
    "armor.yaml": Armor,
    "items.yaml": Item,
    "spellbooks.yaml": SpellBook,
    "scrolls.yaml": Scroll,
    "instruments.yaml": Instrument,
    "skills.yaml": Skill,
    "characters.yaml": Character,
    "creatures.yaml": Creature,
    "lore.yaml": LoreEntry,
}

# поля-ссылки на другие карточки каталога (по id) — резолвятся вторым проходом
_SINGLE_REF_FIELDS = ("equipped_weapon", "equipped_armor", "grants_skill", "teaches_skill")
_LIST_REF_FIELDS = ("inventory", "skills")

_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def _build_effect(spec: dict) -> Effect:
    return Effect(**spec)


def _build_ability(spec: dict) -> Ability:
    return Ability(**spec)


def load_catalog() -> dict[str, Card]:
    """Прочитать все YAML-файлы каталога и построить ORM-объекты.

    Возвращает ``dict`` id-карточки -> ORM-объект (не сохранённый в БД —
    сохранение остаётся на вызывающей стороне, см. ``db.seed.seed_all``).
    """
    cat: dict[str, Card] = {}
    pending_refs: dict[str, dict] = {}

    for filename, model in _MODEL_FOR_FILE.items():
        path = CATALOG_DIR / filename
        entries = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for key, raw_fields in entries.items():
            fields = dict(raw_fields)
            effects = [_build_effect(spec) for spec in fields.pop("effects", [])]
            abilities = [_build_ability(spec) for spec in fields.pop("abilities", [])]
            refs = {
                field: fields.pop(field)
                for field in (*_SINGLE_REF_FIELDS, *_LIST_REF_FIELDS)
                if field in fields
            }
            cat[key] = model(**fields, effects=effects, abilities=abilities)
            pending_refs[key] = refs

    for key, refs in pending_refs.items():
        obj = cat[key]
        for field in _SINGLE_REF_FIELDS:
            if field in refs:
                setattr(obj, field, cat[refs[field]])
        for field in _LIST_REF_FIELDS:
            if field in refs:
                setattr(obj, field, [cat[ref_key] for ref_key in refs[field]])

    return cat


def _find_source_image(card_type: str, key: str) -> Path | None:
    for ext in _IMAGE_EXTENSIONS:
        candidate = IMAGES_DIR / card_type / f"{key}{ext}"
        if candidate.is_file():
            return candidate
    return None


def sync_pregenerated_images(cat: dict[str, Card]) -> None:
    """Подхватить готовые изображения из ``data/images/`` в статику.

    Для каждой карточки без ``image_id`` ищем файл
    ``data/images/<card_type>/<id>.<ext>``; если найден — копируем в
    ``web/static/images/cards/<card_type>/`` (тот же путь, что использует
    ``web/image_gen.py``/``web/serialize.py``) и проставляем ``image_id``.
    """
    import shutil

    for key, card in cat.items():
        if card.image_id:
            continue
        source = _find_source_image(card.card_type, key)
        if source is None:
            continue
        dest_dir = STATIC_CARD_IMAGES_DIR / card.card_type
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / source.name
        if not dest.is_file():
            shutil.copyfile(source, dest)
        card.image_id = f"{card.card_type}/{source.name}"
