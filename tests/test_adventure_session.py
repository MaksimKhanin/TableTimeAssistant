"""Тесты оркестрации приключения: старт, заземление сцены, зачистка, дообогащение.

LLM и эмбеддер замоканы: системная LLM возвращает заранее заданный интент,
нарратор — фиксированный поток дельт и запоминает переданный ему промт.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from grokhanika.adventure import embeddings, retrieval, scene
from grokhanika.adventure import session as advsession
from grokhanika.db import init_db, make_engine, make_session_factory, seed_all

_VOCAB = [
    "импродор", "город", "горожан", "стражник", "трактир", "таверн", "лес",
    "чернолес", "некромант", "гильдия", "караван", "гоблин", "курган", "вельг", "деревн",
]


def _fake_embed(texts, model_name, *, kind="passage"):
    vecs = []
    for text in texts:
        low = text.lower()
        feat = np.array([float(low.count(tok)) for tok in _VOCAB], dtype="float32")
        norm = np.linalg.norm(feat)
        if norm > 0:
            feat = feat / norm
        vecs.append(feat)
    return np.asarray(vecs, dtype="float32")


class _FakeNarrator:
    def __init__(self):
        self.last_messages = None

    def stream(self, messages):
        self.last_messages = messages
        for chunk in ("ГМ ", "ведёт ", "повествование."):
            yield chunk


class _FakeSystem:
    """Системная LLM: для json_mode возвращает интент, иначе — сводку."""

    def __init__(self, intent_payload: dict):
        self.intent_payload = intent_payload

    def chat(self, messages, *, json_mode=False, temperature=None):
        if json_mode:
            return json.dumps(self.intent_payload)
        return "Краткая сводка кампании."


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setattr(embeddings, "embed", _fake_embed)
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    sess = factory()
    seed_all(sess)
    retrieval.reindex(sess)

    narrator = _FakeNarrator()
    holder = {"intent": {}}

    def fake_client_for(_session, role):
        if role == "narrator":
            return narrator
        return _FakeSystem(holder["intent"])

    monkeypatch.setattr(advsession, "client_for", fake_client_for)
    yield sess, narrator, holder
    sess.close()


def _party_ids(sess):
    from grokhanika.db.models import Character

    chars = sess.query(Character).filter(Character.is_player.is_(True)).all()
    return [c.id for c in chars[:2]]


def test_start_adventure_sets_prompt_and_party(env):
    sess, _narrator, _holder = env
    adv = advsession.start_adventure(
        sess,
        description="Партия прибывает в Импродор",
        character_ids=_party_ids(sess),
        goal="Найти заказчика",
        adventure_type="city",
    )
    assert adv.status == "active"
    assert len(adv.party) == 2
    assert "Гейм-мастер" in adv.system_prompt
    assert "Найти заказчика" in adv.system_prompt


def _pin_gorozhanin_on_npc_search(monkeypatch):
    """Заставить поиск NPC детерминированно находить «Горожанин» (без опоры на то, как
    грубый тестовый bag-of-words эмбеддер разрешает точные ничьи score между близкими
    карточками — это забота test_retrieval.py, а не логики оркестрации сцены)."""
    from grokhanika.adventure import retrieval
    from grokhanika.db.models import Creature

    real_search = retrieval.semantic_search

    def fake_search(session, query, *, card_types=None, **kwargs):
        if card_types:
            card = session.query(Creature).filter(Creature.name == "Горожанин").one()
            return [{"card": card, "score": 0.9}]
        return real_search(session, query, card_types=card_types, **kwargs)

    monkeypatch.setattr(retrieval, "semantic_search", fake_search)


def test_intro_grounds_location_and_persists(env, monkeypatch):
    sess, narrator, holder = env
    _pin_gorozhanin_on_npc_search(monkeypatch)
    # локация/начальные NPC решаются детерминированно интент-анализатором (не RAG-поиском)
    holder["intent"] = {
        "location_name": "Импродор",
        "location_description": "Торговый город на перекрёстке дорог",
        "npc_mentions": [{"query": "горожанин", "count": 2}],
    }
    adv = advsession.start_adventure(
        sess,
        description="Партия прибывает в торговый Импродор",
        character_ids=_party_ids(sess),
        goal="осмотреться",
    )
    events = list(advsession.stream_intro(sess, adv))
    kinds = [e["type"] for e in events]
    assert "delta" in kinds and "scene" in kinds and "done" in kinds

    # вводная сохранена как сообщение ГМ
    assert any(m.role == "gm" for m in adv.messages)
    # локация закреплена свободным текстом, не карточкой каталога
    scene_data = scene.serialize_scene(adv)
    assert scene_data["location"] is not None
    assert scene_data["location"]["name"] == "Импродор"
    npc_names = [n["name"] for n in scene_data["npcs"]]
    assert "Горожанин" in npc_names
    assert next(n["count"] for n in scene_data["npcs"] if n["name"] == "Горожанин") == 2


def test_play_turn_grounds_npc_and_location(env, monkeypatch):
    sess, narrator, holder = env
    _pin_gorozhanin_on_npc_search(monkeypatch)
    adv = advsession.start_adventure(
        sess, description="город", character_ids=_party_ids(sess), goal="дела"
    )
    holder["intent"] = {
        "intent_type": "movement",
        "leaves_location": True,
        "location_name": "Импродор",
        "location_description": "город",
        "npc_mentions": [{"query": "горожанин", "count": 1}],
        "search_queries": ["город", "горожане"],
    }
    events = list(advsession.play_turn(sess, adv, adv.party[0].id, "иду в город к горожанам"))
    assert any(e["type"] == "intent" for e in events)
    assert any(e["type"] == "done" for e in events)

    scene_data = scene.serialize_scene(adv)
    npc_names = [n["name"] for n in scene_data["npcs"]]
    assert "Горожанин" in npc_names
    assert scene_data["location"] and scene_data["location"]["name"] == "Импродор"

    # интент сохранён в реплике игрока
    player_msgs = [m for m in adv.messages if m.role == "player"]
    assert player_msgs and player_msgs[-1].intent_json["leaves_location"] is True


def test_leaves_location_clears_previous_npcs(env):
    sess, narrator, holder = env
    adv = advsession.start_adventure(
        sess, description="старт", character_ids=_party_ids(sess), goal="идти"
    )
    # вручную закрепим NPC в сцене
    from grokhanika.db.models import Creature

    goblin = sess.query(Creature).filter(Creature.name == "Гоблин").one()
    scene.pin_card(sess, adv, goblin, scene.KIND_NPC)
    sess.commit()
    assert any(n["name"] == "Гоблин" for n in scene.serialize_scene(adv)["npcs"])

    # уход из локации + запрос, который ничего не находит → старый NPC уходит
    holder["intent"] = {"leaves_location": True, "search_queries": ["абракадабра-пустота"]}
    list(advsession.play_turn(sess, adv, adv.party[0].id, "ухожу прочь в никуда"))
    assert all(n["name"] != "Гоблин" for n in scene.serialize_scene(adv)["npcs"])


def test_skill_check_enriches_prompt(env):
    sess, narrator, holder = env
    adv = advsession.start_adventure(
        sess, description="старт", character_ids=_party_ids(sess), goal="идти"
    )
    holder["intent"] = {
        "intent_type": "skill_check",
        "requires_roll": True,
        "roll_type": "взлом",
        "search_queries": [],
    }
    list(advsession.play_turn(sess, adv, adv.party[0].id, "пытаюсь взломать замок"))
    system_msg = narrator.last_messages[0]["content"]
    assert "проверки" in system_msg and "взлом" in system_msg


def test_resolve_combat_narrates_and_clears_defeated(env):
    sess, narrator, _holder = env
    adv = advsession.start_adventure(
        sess, description="старт", character_ids=_party_ids(sess), goal="идти"
    )
    from grokhanika.db.models import Creature

    goblin = sess.query(Creature).filter(Creature.name == "Гоблин").one()
    scene.pin_card(sess, adv, goblin, scene.KIND_NPC)
    sess.commit()

    outcome = {
        "winner": "party",
        "winner_label": "Союзники",
        "ended_by": "rout",
        "survivors": {"party": ["Герой"], "enemy": []},
        "log": ["Герой бьёт Гоблина: 12 урона", "Гоблин повержен"],
    }
    events = list(advsession.resolve_combat(sess, adv, outcome, [goblin.id]))

    assert any(e["type"] == "done" for e in events)
    assert any(m.role == "gm" for m in adv.messages)

    npc_names = [n["name"] for n in scene.serialize_scene(adv)["npcs"]]
    assert "Гоблин" not in npc_names

    kickoff = narrator.last_messages[-1]["content"]
    assert "Союзники" in kickoff


def test_combat_initiation_with_candidates_emits_combat_ready(env):
    sess, narrator, holder = env
    adv = advsession.start_adventure(
        sess, description="старт", character_ids=_party_ids(sess), goal="идти"
    )
    holder["intent"] = {
        "intent_type": "combat",
        "combat_initiation": True,
        "enemy_query": "гоблин",
        "enemy_count": 1,
        "search_queries": [],
    }
    events = list(advsession.play_turn(sess, adv, adv.party[0].id, "атакую гоблина"))
    system_msg = narrator.last_messages[0]["content"]
    assert "боев" in system_msg.lower()

    combat_events = [e for e in events if e["type"] == "combat_ready"]
    assert combat_events, "ожидалось событие combat_ready"
    assert "Гоблин" in combat_events[0]["enemy_names"]
    assert combat_events[0]["enemy_ids"]

    # найденный противник сразу закреплён в сцене
    npc_names = [n["name"] for n in scene.serialize_scene(adv)["npcs"]]
    assert "Гоблин" in npc_names


def test_combat_initiation_without_candidates_reroutes_narrative(env):
    sess, narrator, holder = env
    adv = advsession.start_adventure(
        sess, description="старт", character_ids=_party_ids(sess), goal="идти"
    )
    # ни enemy_query, ни search_queries — подбор противников не запускается вовсе
    holder["intent"] = {"intent_type": "combat", "combat_initiation": True, "search_queries": []}
    events = list(advsession.play_turn(sess, adv, adv.party[0].id, "атакую пустоту"))
    system_msg = narrator.last_messages[0]["content"]
    assert "стычка не состоялась" in system_msg.lower()
    assert not any(e["type"] == "combat_ready" for e in events)


def test_combat_initiation_without_candidates_suppresses_roll_note(env):
    # regression: combat_initiation + requires_roll без найденного противника раньше
    # склеивали противоречивые инструкции — "боя не было" и "сделай бросок атаки" сразу.
    sess, narrator, holder = env
    adv = advsession.start_adventure(
        sess, description="старт", character_ids=_party_ids(sess), goal="идти"
    )
    holder["intent"] = {
        "intent_type": "combat",
        "combat_initiation": True,
        "requires_roll": True,
        "roll_type": "attack",
        "search_queries": [],
    }
    list(advsession.play_turn(sess, adv, adv.party[0].id, "атакую стражника"))
    system_msg = narrator.last_messages[0]["content"].lower()
    assert "стычка не состоялась" in system_msg
    assert "сделай бросок" not in system_msg
    # (attack) — метка проверки из enrichment-заметки, а не из статичной персоны ГМ
    # (та тоже упоминает "требует проверки", но без этой динамической метки)
    assert "проверки (attack)" not in system_msg
