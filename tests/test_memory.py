"""Тесты управления контекстом: компактинг и эпизодическая память."""
from __future__ import annotations

import numpy as np
import pytest

from grokhanika.adventure import embeddings, memory, retrieval
from grokhanika.adventure import session as advsession
from grokhanika.db import init_db, make_engine, make_session_factory, seed_all

_VOCAB = ["ключ", "дверь", "мост", "река", "башня", "огонь", "лес", "город"]


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


class _FakeSystem:
    def chat(self, messages, *, json_mode=False, temperature=None):
        return "Свёрнутая сводка кампании."


@pytest.fixture()
def adv_env(monkeypatch):
    monkeypatch.setattr(embeddings, "embed", _fake_embed)
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    sess = make_session_factory(engine)()
    seed_all(sess)
    from grokhanika.db.models import Character

    ids = [c.id for c in sess.query(Character).filter(Character.is_player.is_(True)).all()[:1]]
    adv = advsession.start_adventure(sess, description="d", character_ids=ids, goal="g")
    yield sess, adv
    sess.close()


def test_maybe_compact_folds_old_turns(adv_env):
    sess, adv = adv_env
    cfg = {"window_messages": 16, "compact_threshold": 24}
    # 45 ходов: за окном (16) остаётся 29 несвёрнутых ≥ порога 24
    for i in range(45):
        advsession._save_message(sess, adv, role="gm", content=f"ход номер {i}")
    sess.commit()

    changed = memory.maybe_compact(sess, adv, _FakeSystem(), cfg=cfg)
    assert changed is True
    assert adv.running_summary == "Свёрнутая сводка кампании."
    assert adv.summarized_through_message_id is not None

    # повторный вызов без новых ходов ничего не сворачивает
    assert memory.maybe_compact(sess, adv, _FakeSystem(), cfg=cfg) is False


def test_maybe_compact_below_threshold_noop(adv_env):
    sess, adv = adv_env
    cfg = {"window_messages": 16, "compact_threshold": 24}
    for i in range(10):
        advsession._save_message(sess, adv, role="gm", content=f"ход {i}")
    sess.commit()
    assert memory.maybe_compact(sess, adv, _FakeSystem(), cfg=cfg) is False
    assert adv.running_summary == ""


def test_episodic_recall_finds_relevant_turn(adv_env):
    sess, adv = adv_env
    model = "fake"
    m1 = advsession._save_message(sess, adv, role="gm", content="Партия нашла старый ключ у моста.")
    m2 = advsession._save_message(sess, adv, role="gm", content="В таверне шумно и людно.")
    sess.commit()
    memory.record_turn(sess, adv, m1, model_name=model)
    memory.record_turn(sess, adv, m2, model_name=model)
    sess.commit()

    recalled = memory.episodic_recall(
        sess, adv, "где тот ключ от двери", top_k=1, model_name=model, exclude_ids=set()
    )
    assert recalled
    assert "ключ" in recalled[0]
