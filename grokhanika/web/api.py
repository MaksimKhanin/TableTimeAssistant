"""JSON-API админ-UI: категории, карточки, формы, симуляция боя.

Контракт намеренно «чистый» (данные на вход, данные на выход) — фронтенд можно
заменить хоть на React с анимациями, не трогая бэкенд и движок.
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from ..enums import CardType
from . import image_gen, repository, schema
from .serialize import serialize_card
from .simulation import run_simulation, start_interactive, submit_action, submit_roll
from sqlalchemy import select
from ..db.models import Card, Skill as SkillModel, Weapon, Armor, Item, SpellBook, Scroll, Instrument

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
        for fld in data["fields"]:
            if fld["choices_source"]:
                fld["choices"] = repository.choices_for(session, fld["choices_source"])
        payload.append(data)
    return jsonify(payload)


@api.delete("/cards/<int:card_id>")
def delete_card(card_id: int):
    """Удалить карточку. 404 если не найдена, 409 если на неё ссылаются другие карточки."""
    try:
        found = repository.delete_card(_session(), card_id)
    except Exception as exc:
        return jsonify({"error": f"Невозможно удалить: {exc}"}), 409
    if not found:
        return jsonify({"error": "карточка не найдена"}), 404
    return "", 204


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


@api.patch("/cards/<int:card_id>")
def update_card(card_id: int):
    """Обновить карточку по id. 400 + {errors} при невалидных данных, 404 если не найдена."""
    body = request.get_json(silent=True) or {}
    card_type = body.get("card_type")
    if card_type not in schema.CARD_FORMS:
        return jsonify({"errors": {"__form__": "Не указан корректный тип карточки"}}), 400
    try:
        updated = repository.update_card(_session(), card_id, card_type, body)
    except repository.UpdateError as exc:
        return jsonify({"errors": exc.errors}), 400
    if updated is None:
        return jsonify({"error": "карточка не найдена"}), 404
    return jsonify(updated)


# ───────────────────────── генерация изображений ─────────────────────────


@api.get("/settings/image")
def image_settings_get():
    """Настройки модели генерации изображений (эндпоинт/модель/ключ/стиль)."""
    return jsonify(image_gen.get_config(_session()))


@api.put("/settings/image")
def image_settings_put():
    body = request.get_json(silent=True) or {}
    return jsonify(image_gen.save_config(_session(), body))


@api.post("/settings/image/test")
def image_settings_test():
    """Health-check эндпоинта генерации изображений (с учётом переданных правок)."""
    body = request.get_json(silent=True) or {}
    cfg = {**image_gen.get_config(_session()), **body}
    client = image_gen.ImageGenClient(
        base_url=cfg.get("base_url", ""),
        model=cfg.get("model", ""),
        api_key=cfg.get("api_key", ""),
        size=cfg.get("size", "1024x1024"),
    )
    return jsonify(client.health_check())


@api.post("/cards/<int:card_id>/regenerate-image")
def regenerate_card_image(card_id: int):
    """Перегенерировать арт карточки по описанию (кнопка в админке)."""
    try:
        result = repository.regenerate_card_image(_session(), card_id)
    except image_gen.ImageGenError as exc:
        return jsonify({"error": str(exc)}), 502
    if result is None:
        return jsonify({"error": "карточка не найдена"}), 404
    return jsonify(result)


# ───────────────────────── состояние группы ─────────────────────────


@api.get("/party")
def party_state():
    """Все игровые персонажи с инвентарём и экипировкой (экран состояния группы)."""
    return jsonify(repository.get_party(_session()))


@api.post("/characters/<int:char_id>/equip")
def equip_character(char_id: int):
    """Экипировать или снять предмет у персонажа.
    Тело: {"slot": "weapon"|"armor", "card_id": int|null}"""
    body = request.get_json(silent=True) or {}
    slot = body.get("slot")
    card_id = body.get("card_id")
    try:
        result = repository.equip_character(_session(), char_id, slot, card_id)
    except repository.CreateError as exc:
        return jsonify({"errors": exc.errors}), 400
    return jsonify(result)


@api.post("/characters/<int:char_id>/inventory")
def add_inventory_item(char_id: int):
    """Добавить предмет в инвентарь персонажа. Тело: {"item_id": int}"""
    body = request.get_json(silent=True) or {}
    item_id = body.get("item_id")
    if not item_id:
        return jsonify({"error": "item_id обязателен"}), 400
    try:
        result = repository.add_to_inventory(_session(), char_id, int(item_id))
    except repository.CreateError as exc:
        return jsonify({"errors": exc.errors}), 400
    if result is None:
        return jsonify({"error": "Персонаж не найден"}), 404
    return jsonify(result)


@api.delete("/characters/<int:char_id>/inventory/<int:item_id>")
def remove_inventory_item(char_id: int, item_id: int):
    """Убрать предмет из инвентаря персонажа."""
    result = repository.remove_from_inventory(_session(), char_id, item_id)
    if result is None:
        return jsonify({"error": "Персонаж не найден"}), 404
    return jsonify(result)


@api.post("/characters/<int:char_id>/skills")
def add_character_skill(char_id: int):
    """Добавить навык персонажу. Тело: {"skill_id": int}"""
    body = request.get_json(silent=True) or {}
    skill_id = body.get("skill_id")
    if not skill_id:
        return jsonify({"error": "skill_id обязателен"}), 400
    try:
        result = repository.add_skill_to_character(_session(), char_id, int(skill_id))
    except repository.CreateError as exc:
        return jsonify({"errors": exc.errors}), 400
    if result is None:
        return jsonify({"error": "Персонаж не найден"}), 404
    return jsonify(result)


@api.delete("/characters/<int:char_id>/skills/<int:skill_id>")
def remove_character_skill(char_id: int, skill_id: int):
    """Убрать навык у персонажа."""
    result = repository.remove_skill_from_character(_session(), char_id, skill_id)
    if result is None:
        return jsonify({"error": "Персонаж не найден"}), 404
    return jsonify(result)


@api.get("/items-catalog")
def items_catalog():
    """Все предметы, которые можно добавить в инвентарь персонажа."""
    session = _session()
    allowed_types = ("weapon", "armor", "item", "spellbook", "scroll", "instrument")
    from sqlalchemy import select
    from ..db.models import Card as CardModel
    cards = session.execute(
        select(CardModel).where(CardModel.card_type.in_(allowed_types)).order_by(CardModel.name)
    ).scalars().all()
    return jsonify([{"id": c.id, "name": c.name, "card_type": c.card_type} for c in cards])


@api.get("/skills-catalog")
def skills_catalog():
    """Все навыки в системе."""
    session = _session()
    from sqlalchemy import select
    from ..db.models import Card as CardModel
    skills = session.execute(
        select(CardModel).where(CardModel.card_type == "skill").order_by(CardModel.name)
    ).scalars().all()
    return jsonify([{"id": s.id, "name": s.name} for s in skills])


@api.get("/equipment")
def equipment():
    """Всё оружие и броня в системе — для выбора экипировки."""
    return jsonify(repository.list_equipment(_session()))


# ───────────────────────── симуляция боя ─────────────────────────


@api.get("/roster")
def roster():
    """Доступные для боя участники: герои, NPC и существа."""
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


# ───────────────────────── интерактивный бой ─────────────────────────


@api.post("/battle/start")
def battle_start():
    """Начать интерактивный бой: вернуть начальное состояние + первый ход игрока."""
    body = request.get_json(silent=True) or {}
    ally_ids = [int(x) for x in body.get("allies", [])]
    enemy_ids = [int(x) for x in body.get("enemies", [])]
    seed = body.get("seed")
    seed = int(seed) if seed not in (None, "") else None
    try:
        result = start_interactive(_session(), ally_ids, enemy_ids, seed=seed)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@api.post("/battle/<battle_id>/action")
def battle_action(battle_id: str):
    """Принять действие игрока; вернуть новые события и следующий ход игрока."""
    body = request.get_json(silent=True) or {}
    try:
        result = submit_action(battle_id, body)
    except KeyError:
        return jsonify({"error": "Сессия боя не найдена — возможно, бой уже завершён"}), 404
    return jsonify(result)


@api.post("/battle/<battle_id>/roll")
def battle_roll(battle_id: str):
    """Принять значение ожидаемого броска игрока.

    Тело: {"value": int} — ручной ввод реального кубика; {"value": null} — автобросок.
    Ответ: как у /action, плюс "roll_result" (итог броска) и, если нужен следующий
    бросок (урон после попадания), статус "roll" с его описанием."""
    body = request.get_json(silent=True) or {}
    value = body.get("value")
    value = int(value) if value not in (None, "") else None
    try:
        result = submit_roll(battle_id, value)
    except KeyError:
        return jsonify({"error": "Сессия боя не найдена — возможно, бой уже завершён"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)
