"""Тесты семантического поиска (RAG) с детерминированным мок-эмбеддером.

Чтобы не тянуть torch/sentence-transformers в CI, подменяем
``grokhanika.adventure.embeddings.embed`` на простой bag-of-words по фиксированному
словарю русских стемов — косинус остаётся осмысленным.
"""
from __future__ import annotations

import numpy as np
import pytest

from grokhanika.adventure import embeddings, retrieval
from grokhanika.db import init_db, make_engine, make_session_factory, seed_all
from grokhanika.enums import CardType

# словарь стемов: признак = число вхождений стема как подстроки
_VOCAB = [
    "город", "горожан", "стражник", "трактир", "таверн", "лес", "некромант",
    "гильдия", "караван", "гоблин", "курган", "деревн", "оружей", "мертвец",
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


@pytest.fixture()
def session(monkeypatch):
    monkeypatch.setattr(embeddings, "embed", _fake_embed)
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    sess = factory()
    seed_all(sess)
    retrieval.reindex(sess)
    yield sess
    sess.close()


def test_reindex_counts_indexable(session):
    n = retrieval.reindex(session)
    assert n > 0
    # лор (6) + NPC/персонажи/предметы/оружие/броня; точное число не фиксируем,
    # но лор-записи должны быть проиндексированы
    from grokhanika.db.models import Embedding

    lore_vecs = (
        session.query(Embedding).filter(Embedding.entity_type == retrieval.ENTITY_LORE).count()
    )
    assert lore_vecs == 6


def test_city_query_finds_city_and_citizen(session):
    hits = retrieval.semantic_search(
        session, "хочу посетить город и поговорить с горожанами", top_k=6
    )
    names = [h["card"].name for h in hits]
    assert "Импродор" in names  # локация-город из лора
    assert "Горожанин" in names  # NPC-карточка


def test_card_types_filter_returns_only_creatures(session):
    hits = retrieval.semantic_search(
        session,
        "городской стражник у ворот",
        card_types=[CardType.CREATURE.value],
        top_k=5,
    )
    assert hits, "ожидали хотя бы одно совпадение"
    assert all(h["card"].card_type == CardType.CREATURE.value for h in hits)
    assert hits[0]["card"].name == "Городской стражник"


def test_lore_only_search(session):
    hits = retrieval.semantic_search(
        session,
        "древний лес и некромант с мертвецами",
        entity_types=[retrieval.ENTITY_LORE],
        top_k=3,
    )
    assert hits
    assert all(h["card"].card_type == CardType.LORE.value for h in hits)
    assert "Чернолесье" in [h["card"].name for h in hits]


def test_empty_query_returns_nothing(session):
    assert retrieval.semantic_search(session, "   ") == []


def test_reindex_iter_reports_progress_and_matches_reindex_count(session):
    events = list(retrieval.reindex_iter(session))
    assert events[0]["type"] == "start"
    total = events[0]["total"]
    assert total > 0

    progress = [e for e in events if e["type"] == "progress"]
    assert [e["done"] for e in progress] == list(range(1, total + 1))
    assert all(e["total"] == total for e in progress)
    assert all(e["name"] for e in progress)  # у каждого события есть имя карточки

    assert events[-1] == {"type": "done", "count": total}
    assert retrieval.reindex(session) == total
