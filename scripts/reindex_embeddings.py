"""Пересчитать векторные эмбеддинги карточек и лора для семантического поиска (RAG).

Требует установленный экстра ``adventure`` (sentence-transformers и пр.). Эмбеддер
скачивается с HuggingFace при первом запуске.

Запуск:  python -m scripts.reindex_embeddings [путь_к_бд]
"""
from __future__ import annotations

import sys

from grokhanika.adventure import retrieval
from grokhanika.db import DEFAULT_DB_URL, init_db, make_engine, make_session_factory


def main(db_url: str = DEFAULT_DB_URL) -> None:
    engine = make_engine(db_url)
    init_db(engine)  # на случай отсутствия таблицы embeddings
    factory = make_session_factory(engine)
    with factory() as session:
        count = retrieval.reindex(session)
    print(f"Проиндексировано карточек/лора: {count}")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_URL
    main(url if "://" in url else f"sqlite:///{url}")
