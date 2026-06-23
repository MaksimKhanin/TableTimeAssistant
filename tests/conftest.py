"""Общие фикстуры тестов."""
from __future__ import annotations

import random

import pytest

from grokhanika.db import init_db, make_engine, make_session_factory, seed_all


class ScriptedRandom:
    """Детерминированный ГПСЧ: отдаёт заранее заданные значения.

    ``randint`` берёт значения из очереди ``ints`` (по исчерпании — минимум ``a``,
    т.е. кубики падают на минимум). ``random`` берёт из очереди ``floats``
    (по исчерпании — 0.0).
    """

    def __init__(self, ints=None, floats=None):
        self._ints = list(ints or [])
        self._floats = list(floats or [])

    def randint(self, a: int, b: int) -> int:
        if self._ints:
            return self._ints.pop(0)
        return a

    def random(self) -> float:
        if self._floats:
            return self._floats.pop(0)
        return 0.0


@pytest.fixture
def session():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    s = factory()
    s.info["catalog"] = seed_all(s)
    yield s
    s.close()


@pytest.fixture
def catalog(session):
    return session.info["catalog"]


@pytest.fixture
def rng():
    return random.Random(20260623)
