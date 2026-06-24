"""Flask-приложение админ-UI «Гроханики».

Фабрика создаёт движок БД и фабрику сессий, наполняет пустую БД сидом и
регистрирует JSON-API (см. :mod:`grokhanika.web.api`). Состояние боя в БД не
пишется — симуляция работает на снимках карточек (``Combatant``).
"""
from __future__ import annotations

import os
from typing import Optional

from flask import Flask, g, render_template
from sqlalchemy import select

from ..db import init_db, make_engine, make_session_factory, seed_all
from ..db.models import Card
from .api import api

DEFAULT_WEB_DB_URL = "sqlite:///grokhanika.db"


def _ensure_seeded(session_factory) -> None:
    """Если БД пуста — наполнить сид-данными (демо-каталог)."""
    with session_factory() as session:
        has_any = session.execute(select(Card.id).limit(1)).first()
        if has_any is None:
            seed_all(session)


def create_app(
    db_url: Optional[str] = None,
    *,
    seed: bool = True,
    session_factory=None,
) -> Flask:
    """Собрать Flask-приложение.

    ``session_factory`` можно передать снаружи (тесты используют общую in-memory
    БД). Иначе движок создаётся по ``db_url`` / переменной ``GROKHANIKA_DB_URL``.
    """
    app = Flask(__name__)

    if session_factory is None:
        url = db_url or os.environ.get("GROKHANIKA_DB_URL", DEFAULT_WEB_DB_URL)
        engine = make_engine(url)
        init_db(engine)
        session_factory = make_session_factory(engine)
        if seed:
            _ensure_seeded(session_factory)

    app.config["SESSION_FACTORY"] = session_factory

    @app.before_request
    def _open_session() -> None:
        g.session = app.config["SESSION_FACTORY"]()

    @app.teardown_request
    def _close_session(exc) -> None:
        session = g.pop("session", None)
        if session is not None:
            if exc is not None:
                session.rollback()
            session.close()

    app.register_blueprint(api)

    @app.route("/")
    def index():
        return render_template("index.html")

    return app
