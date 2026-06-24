"""Запустить веб-UI «Гроханики» (админка карточек + симулятор боя).

Запуск:  python -m scripts.run_web [--host H] [--port P] [--db sqlite:///grokhanika.db]

БД по умолчанию — grokhanika.db (создаётся и наполняется сидом, если пустая).
"""
from __future__ import annotations

import argparse

from grokhanika.web import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Веб-UI «Гроханики»")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--db", default=None, help="URL БД (по умолчанию grokhanika.db)")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app(db_url=args.db)
    print(f"UI «Гроханики»: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
