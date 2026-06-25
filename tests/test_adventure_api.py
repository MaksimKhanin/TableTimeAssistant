"""Тесты JSON/SSE-API приключения через Flask test client (LLM/эмбеддер замоканы)."""
from __future__ import annotations

import json

import numpy as np
import pytest

from grokhanika.adventure import embeddings, retrieval
from grokhanika.adventure import session as advsession
from grokhanika.db import init_db, make_engine, make_session_factory, seed_all
from grokhanika.web.app import create_app

_VOCAB = ["импродор", "город", "горожан", "стражник", "лес", "некромант", "гоблин"]


def _fake_embed(texts, model_name, *, kind="passage"):
    out = []
    for t in texts:
        low = t.lower()
        v = np.array([float(low.count(tok)) for tok in _VOCAB], dtype="float32")
        n = np.linalg.norm(v)
        if n:
            v = v / n
        out.append(v)
    return np.asarray(out, dtype="float32")


class _FakeNarrator:
    def stream(self, messages):
        yield "Ты "
        yield "в городе."


class _FakeSystem:
    def __init__(self, payload):
        self.payload = payload

    def chat(self, messages, *, json_mode=False, temperature=None):
        return json.dumps(self.payload) if json_mode else "сводка"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(embeddings, "embed", _fake_embed)
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        seed_all(s)
        retrieval.reindex(s)

    holder = {"intent": {"search_queries": ["город", "горожане"], "leaves_location": True}}

    def fake_client_for(_session, role):
        return _FakeNarrator() if role == "narrator" else _FakeSystem(holder["intent"])

    monkeypatch.setattr(advsession, "client_for", fake_client_for)

    app = create_app(session_factory=factory)
    app.config.update(TESTING=True)
    return app.test_client(), factory, holder


def _frames(resp):
    return [
        json.loads(line[5:].strip())
        for line in resp.get_data(as_text=True).splitlines()
        if line.startswith("data:")
    ]


def _party_ids(factory):
    from grokhanika.db.models import Character

    with factory() as s:
        return [c.id for c in s.query(Character).filter(Character.is_player.is_(True)).all()[:2]]


def test_presets(client):
    c, _factory, _holder = client
    resp = c.get("/api/adventure/presets")
    assert resp.status_code == 200
    assert any(p["id"] == "city" for p in resp.get_json())


def test_start_and_get(client):
    c, factory, _holder = client
    resp = c.post(
        "/api/adventure/start",
        json={"description": "Партия в Импродоре", "character_ids": _party_ids(factory),
              "goal": "найти заказчика", "adventure_type": "city"},
    )
    assert resp.status_code == 201
    sid = resp.get_json()["session_id"]

    got = c.get(f"/api/adventure/{sid}").get_json()
    assert len(got["party"]) == 2
    assert got["status"] == "active"


def test_start_requires_party(client):
    c, _factory, _holder = client
    resp = c.post("/api/adventure/start", json={"description": "x", "character_ids": []})
    assert resp.status_code == 400


def test_intro_stream_grounds_location(client):
    c, factory, _holder = client
    sid = c.post(
        "/api/adventure/start",
        json={"description": "Партия прибывает в торговый Импродор",
              "character_ids": _party_ids(factory), "goal": "осмотреться"},
    ).get_json()["session_id"]

    resp = c.get(f"/api/adventure/{sid}/intro")
    assert resp.status_code == 200
    frames = _frames(resp)
    types = [f["type"] for f in frames]
    assert "delta" in types and "done" in types
    scene_frame = next(f for f in frames if f["type"] == "scene")
    assert scene_frame["scene"]["location"]["name"] == "Импродор"


def test_message_stream_pins_npc(client):
    c, factory, holder = client
    sid = c.post(
        "/api/adventure/start",
        json={"description": "город", "character_ids": _party_ids(factory), "goal": "дела"},
    ).get_json()["session_id"]
    c.get(f"/api/adventure/{sid}/intro")  # вводная

    resp = c.post(
        f"/api/adventure/{sid}/message",
        json={"character_id": _party_ids(factory)[0], "text": "иду к горожанам в город"},
    )
    frames = _frames(resp)
    assert any(f["type"] == "intent" for f in frames)
    scene_frame = next(f for f in frames if f["type"] == "scene")
    npc_names = [n["name"] for n in scene_frame["scene"]["npcs"]]
    assert "Горожанин" in npc_names


def test_settings_get_put(client):
    c, _factory, _holder = client
    cfg = c.get("/api/adventure/settings").get_json()
    assert "narrator" in cfg and "system" in cfg and "embedder" in cfg

    resp = c.put("/api/adventure/settings", json={"narrator": {"model": "my-narrator-7b"}})
    assert resp.status_code == 200
    assert resp.get_json()["narrator"]["model"] == "my-narrator-7b"
    # перечитали — сохранилось
    assert c.get("/api/adventure/settings").get_json()["narrator"]["model"] == "my-narrator-7b"


def test_lore_crud(client):
    c, _factory, _holder = client
    base = len(c.get("/api/lore").get_json())

    created = c.post(
        "/api/lore",
        json={"name": "Башня Магов", "description": "Высокая башня на холме", "category": "location"},
    )
    assert created.status_code == 201
    lid = created.get_json()["id"]
    assert len(c.get("/api/lore").get_json()) == base + 1

    upd = c.put(f"/api/lore/{lid}", json={"name": "Башня Магов", "description": "обновлено",
                                          "category": "location"})
    assert upd.status_code == 200
    assert upd.get_json()["description"] == "обновлено"

    assert c.delete(f"/api/lore/{lid}").status_code == 200
    assert len(c.get("/api/lore").get_json()) == base


def test_lore_validation_error(client):
    c, _factory, _holder = client
    resp = c.post("/api/lore", json={"name": "  ", "description": "x"})
    assert resp.status_code == 400
    assert "errors" in resp.get_json()
