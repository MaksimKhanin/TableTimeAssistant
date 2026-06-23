"""Подключение к БД и инициализация схемы (SQLite)."""
from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_DB_URL = "sqlite:///grokhanika.db"


def make_engine(url: str = DEFAULT_DB_URL, *, echo: bool = False) -> Engine:
    return create_engine(url, echo=echo)


def init_db(engine: Engine) -> None:
    """Создать все таблицы."""
    Base.metadata.create_all(engine)


def drop_db(engine: Engine) -> None:
    Base.metadata.drop_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False — объекты остаются пригодны после commit
    return sessionmaker(engine, expire_on_commit=False)
