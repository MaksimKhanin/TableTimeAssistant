"""JSON/SSE-API модуля приключения: сессии, потоковый ход ГМ, настройки LLM, лор.

Контракт «данные на вход — данные на выход», как и в боевом ``api.py``. Ответы ГМ
отдаются потоком Server-Sent Events: кадр ``data: {json}\\n\\n`` с полем ``type``
(``delta``/``intent``/``scene``/``combat_ready``/``done``/``error``). Стриминг обёрнут в
``stream_with_context``, чтобы ``g.session`` жил всё время генерации.

Сам бой (после ``combat_ready``) ведёт боевой API ``/api/battle/start`` и
``/api/battle/<id>/action`` из ``web/api.py`` — здесь только запуск (подбор
противников) и разрешение (LLM-рассказ об итоге, ``/adventure/<id>/battle/resolve``).
"""
from __future__ import annotations

import json

from flask import (
    Blueprint,
    Response,
    current_app,
    g,
    jsonify,
    request,
    stream_with_context,
)

from ..db.models import AdventureSession
from . import config, scene
from . import session as advsession
from .llm import LLMClient
from .presets import load_presets
from ..web.serialize import serialize_card

adventure_api = Blueprint("adventure", __name__, url_prefix="/api")


def _session():
    return g.session


# ───────────────────────── сериализация ─────────────────────────


def _serialize_message(msg) -> dict:
    return {
        "id": msg.id,
        "role": msg.role,
        "speaker": msg.speaker.name if msg.speaker is not None else None,
        "speaker_id": msg.speaker_character_id,
        "content": msg.content,
        "intent": msg.intent_json,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def _serialize_session(adv: AdventureSession, *, full: bool = False) -> dict:
    data = {
        "id": adv.id,
        "title": adv.title,
        "adventure_type": adv.adventure_type,
        "goal": adv.goal,
        "description": adv.description,
        "status": adv.status,
        "created_at": adv.created_at.isoformat() if adv.created_at else None,
        "party": [serialize_card(c) for c in adv.party],
    }
    if full:
        data["messages"] = [_serialize_message(m) for m in adv.messages]
        data["scene"] = scene.serialize_scene(adv)
        data["running_summary"] = adv.running_summary
    return data


# ───────────────────────── SSE-обёртка ─────────────────────────


def _stream_response(work) -> Response:
    """SSE-ответ. ``work(session)`` — генератор событий-словарей.

    Стриминг открывает собственную сессию БД из фабрики приложения: ленивые
    подгрузки ORM во время генерации не зависят от жизненного цикла ``g.session``
    (которая закрывается при teardown запроса до того, как поток будет считан).
    """
    factory = current_app.config["SESSION_FACTORY"]

    def gen():
        session = factory()
        try:
            for event in work(session):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001 - не рвём соединение, сообщаем кадром
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            session.close()

    return Response(
        stream_with_context(gen()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ───────────────────────── сессии приключения ─────────────────────────


@adventure_api.get("/adventure/presets")
def presets():
    return jsonify(load_presets())


@adventure_api.get("/adventure/list")
def adventure_list():
    sessions = (
        _session().query(AdventureSession).order_by(AdventureSession.id.desc()).all()
    )
    return jsonify([_serialize_session(a) for a in sessions])


@adventure_api.post("/adventure/start")
def adventure_start():
    body = request.get_json(silent=True) or {}
    try:
        ids = [int(x) for x in body.get("character_ids", [])]
    except (TypeError, ValueError):
        return jsonify({"error": "некорректный список персонажей"}), 400
    try:
        adv = advsession.start_adventure(
            _session(),
            description=body.get("description", ""),
            character_ids=ids,
            goal=body.get("goal", ""),
            adventure_type=body.get("adventure_type", "custom"),
            title=body.get("title", ""),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"session_id": adv.id, "session": _serialize_session(adv)}), 201


@adventure_api.get("/adventure/<int:adv_id>")
def adventure_get(adv_id: int):
    adv = _session().get(AdventureSession, adv_id)
    if adv is None:
        return jsonify({"error": "приключение не найдено"}), 404
    return jsonify(_serialize_session(adv, full=True))


@adventure_api.get("/adventure/<int:adv_id>/intro")
def adventure_intro(adv_id: int):
    if _session().get(AdventureSession, adv_id) is None:
        return jsonify({"error": "приключение не найдено"}), 404

    def work(session):
        adv = session.get(AdventureSession, adv_id)
        if any(m.role == "gm" for m in adv.messages):
            # вводная уже была — просто отдать текущее состояние
            yield {"type": "scene", "scene": scene.serialize_scene(adv)}
            yield {"type": "done", "message_id": None}
            return
        yield from advsession.stream_intro(session, adv)

    return _stream_response(work)


@adventure_api.post("/adventure/<int:adv_id>/message")
def adventure_message(adv_id: int):
    if _session().get(AdventureSession, adv_id) is None:
        return jsonify({"error": "приключение не найдено"}), 404
    body = request.get_json(silent=True) or {}
    character_id = body.get("character_id")
    character_id = int(character_id) if character_id not in (None, "") else None
    text = body.get("text", "")

    def work(session):
        adv = session.get(AdventureSession, adv_id)
        yield from advsession.play_turn(session, adv, character_id, text)

    return _stream_response(work)


@adventure_api.post("/adventure/<int:adv_id>/roll")
def adventure_roll(adv_id: int):
    """Принять бросок проверки из окна кубика и продолжить повествование.

    Тело: {"roll_type": str, "difficulty": int, "value": int, "auto": bool}.
    Значение уже брошено на стороне UI (ручной ввод реального кубика или
    автобросок с анимацией); сервер фиксирует исход и стримит рассказ ГМ."""
    if _session().get(AdventureSession, adv_id) is None:
        return jsonify({"error": "приключение не найдено"}), 404
    body = request.get_json(silent=True) or {}
    try:
        value = int(body.get("value"))
    except (TypeError, ValueError):
        return jsonify({"error": "value (1..20) обязателен"}), 400
    try:
        difficulty = int(body.get("difficulty") or 0)
    except (TypeError, ValueError):
        difficulty = 0
    roll_type = str(body.get("roll_type") or "")
    auto = bool(body.get("auto"))

    def work(session):
        adv = session.get(AdventureSession, adv_id)
        yield from advsession.resolve_roll(
            session, adv, roll_type=roll_type, value=value, difficulty=difficulty, auto=auto
        )

    return _stream_response(work)


@adventure_api.post("/adventure/<int:adv_id>/battle/resolve")
def adventure_battle_resolve(adv_id: int):
    """Подвести LLM-итог завершившегося боя и вернуться к повествованию."""
    if _session().get(AdventureSession, adv_id) is None:
        return jsonify({"error": "приключение не найдено"}), 404
    body = request.get_json(silent=True) or {}
    outcome = body.get("outcome") or {}
    enemy_ids = body.get("enemy_ids") or []
    try:
        enemy_ids = [int(x) for x in enemy_ids]
    except (TypeError, ValueError):
        enemy_ids = []

    def work(session):
        adv = session.get(AdventureSession, adv_id)
        yield from advsession.resolve_combat(session, adv, outcome, enemy_ids)

    return _stream_response(work)


# ───────────────────────── настройки LLM ─────────────────────────


@adventure_api.get("/adventure/settings")
def settings_get():
    return jsonify(config.get_all(_session()))


@adventure_api.put("/adventure/settings")
def settings_put():
    body = request.get_json(silent=True) or {}
    updated = config.save_sections(_session(), body)
    return jsonify(updated)


@adventure_api.post("/adventure/settings/test")
def settings_test():
    """Health-check эндпоинтов нарратора и системной LLM (с учётом переданных правок)."""
    body = request.get_json(silent=True) or {}
    session = _session()
    result = {}
    for role in ("narrator", "system"):
        cfg = config.get_section(session, role)
        override = body.get(role) or {}
        if isinstance(override, dict):
            cfg = {**cfg, **override}
        client = LLMClient(
            base_url=cfg.get("base_url", ""),
            model=cfg.get("model", ""),
            api_key=cfg.get("api_key", ""),
        )
        result[role] = client.health_check()
    return jsonify(result)


@adventure_api.post("/adventure/reindex-embeddings")
def reindex_embeddings():
    """SSE-поток переиндексации эмбеддингов (кнопка «Переиндексировать» в LLM/RAG)."""

    def work(session):
        try:
            from . import retrieval
        except Exception as exc:  # noqa: BLE001 - например, не установлен sentence-transformers
            yield {"type": "error", "error": f"эмбеддер недоступен: {exc}"}
            return
        try:
            yield from retrieval.reindex_iter(session)
        except Exception as exc:  # noqa: BLE001 - не рвём поток молча
            yield {"type": "error", "error": str(exc)}

    return _stream_response(work)


# ───────────────────────── лор-база (CRUD) ─────────────────────────


@adventure_api.get("/lore")
def lore_list():
    from ..web import repository

    category = request.args.get("category", "all")
    return jsonify(repository.list_lore(_session(), category=category))


@adventure_api.post("/lore")
def lore_create():
    from ..web import repository

    body = request.get_json(silent=True) or {}
    try:
        created = repository.create_lore(_session(), body)
    except repository.CreateError as exc:
        return jsonify({"errors": exc.errors}), 400
    return jsonify(created), 201


@adventure_api.put("/lore/<int:lore_id>")
def lore_update(lore_id: int):
    from ..web import repository

    body = request.get_json(silent=True) or {}
    try:
        updated = repository.update_lore(_session(), lore_id, body)
    except repository.CreateError as exc:
        return jsonify({"errors": exc.errors}), 400
    if updated is None:
        return jsonify({"error": "лор-запись не найдена"}), 404
    return jsonify(updated)


@adventure_api.delete("/lore/<int:lore_id>")
def lore_delete(lore_id: int):
    from ..web import repository

    if not repository.delete_lore(_session(), lore_id):
        return jsonify({"error": "лор-запись не найдена"}), 404
    return jsonify({"ok": True})
