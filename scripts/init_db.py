"""Создать SQLite-БД «Гроханики» и наполнить её сид-данными.

Запуск:  python -m scripts.init_db [путь_к_бд]
"""
from __future__ import annotations

import sys

from grokhanika.db import (
    DEFAULT_DB_URL,
    drop_db,
    init_db,
    make_engine,
    make_session_factory,
    seed_all,
)


def main(db_url: str = DEFAULT_DB_URL) -> None:
    engine = make_engine(db_url)
    drop_db(engine)
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        catalog = seed_all(session)
    print(f"БД готова: {db_url}")
    print(f"Карточек загружено: {len(catalog)}")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_URL
    main(url if "://" in url else f"sqlite:///{url}")
