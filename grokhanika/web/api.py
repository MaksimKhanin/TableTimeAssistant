"""JSON-API админ-UI: категории, карточки, формы, симуляция боя.

Контракт намеренно «чистый» (данные на вход, данные на выход) — фронтенд можно
заменить хоть на React с анимациями, не трогая бэкенд и движок.
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from ..enums import CardType
from . import repository, schema
from .serialize import serialize_card
from .simulation import run_simulation

api = Blueprint("api", __name__, url_prefix="/api")


def _session():
    return g.session


# ───────────────────────── витрина ─────────────────────────


@api.get("/categories")
def categories():
    """Список категорий с их фильтрами и сортировками (для навигации UI)."""
    return jsonify([c.to_dict() for c in schema.CATEGORIES])


@api.get("/cards")
def cards():
    """Карточки категории. Параметры: category, filter, sort, order."""
    category = request.args.get("category", "heroes")
    items = repository.list_category(
        _session(),
        category,
        filter_value=request.args.get("filter", "all"),
        sort=request.args.get("sort", "name"),
        order=request.args.get("order", "asc"),
    )
    return jsonify({"category": category, "items": items})


@api.get("/cards/<int:card_id>")
def card_detail(card_id: int):
    data = repository.get_card(_session(), card_id)
    if data is None:
        return jsonify({"error": "карточка не найдена"}), 404
    return jsonify(data)


# ───────────────────────── формы добавления ─────────────────────────


@api.get("/forms")
def forms():
    """Схемы форм для всех типов карточек + динамические варианты choice-полей."""
    session = _session()
    payload = []
    for card_type, form in schema.CARD_FORMS.items():
        data = form.to_dict()
        # дозаполняем choices для полей со ссылкой на существующие карточки
        for fld in data["fields"]:
            if fld["choices_source"]:
                fld["choices"] = repository.choices_for(session, fld["choices_source"])
        payload.append(data)
    return jsonify(payload)


@api.post("/cards")
def create_card():
    """Создать карточку из данных формы. 400 + {errors} при невалидных данных."""
    body = request.get_json(silent=True) or {}
    card_type = body.get("card_type")
    if card_type not in schema.CARD_FORMS:
        return jsonify({"errors": {"__form__": "Не указан корректный тип карточки"}}), 400
    try:
        created = repository.create_card(_session(), card_type, body)
    except repository.CreateError as exc:
        return jsonify({"errors": exc.errors}), 400
    return jsonify(created), 201


# ───────────────────────── симуляция боя ─────────────────────────


@api.get("/roster")
def roster():
    """Доступные для боя участники: герои, NPC и существа (для выбора сторон)."""
    session = _session()
    heroes = repository.list_category(session, "heroes", sort="name")
    npc = repository.list_category(session, "npc", sort="name")
    return jsonify({"heroes": heroes, "npc": npc})


@api.post("/simulate")
def simulate():
    """Прогнать автобой выбранных союзников против врагов."""
    body = request.get_json(silent=True) or {}
    ally_ids = [int(x) for x in body.get("allies", [])]
    enemy_ids = [int(x) for x in body.get("enemies", [])]
    seed = body.get("seed")
    seed = int(seed) if seed not in (None, "") else None
    try:
        result = run_simulation(_session(), ally_ids, enemy_ids, seed=seed)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)
