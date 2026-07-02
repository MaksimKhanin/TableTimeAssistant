"""Пресеты типов приключения — читаются из ``grokhanika/data/adventures/*.yaml``.

Числовой префикс имени файла задаёт порядок вывода (см. файлы ``00_dungeon.yaml``
... ``09_custom.yaml``). Иконка (если указана и файл существует) отдаётся как
URL статики, собранной из ``data/images/adventures/`` (см.
``grokhanika.web.app._sync_adventure_icons``).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "adventures"
_SOURCE_ICONS_DIR = Path(__file__).resolve().parent.parent / "data" / "images" / "adventures"
_STATIC_ICONS_DIR = (
    Path(__file__).resolve().parent.parent / "web" / "static" / "images" / "adventures"
)


def sync_adventure_icons() -> None:
    """Скопировать готовые иконки приключений в статику (идемпотентно).

    Не завязано на пустоту БД (приключения-пресеты — не карточки в БД) —
    вызывается безусловно при старте приложения, см. ``web/app.py``.
    """
    if not _SOURCE_ICONS_DIR.is_dir():
        return
    _STATIC_ICONS_DIR.mkdir(parents=True, exist_ok=True)
    for source in _SOURCE_ICONS_DIR.iterdir():
        if not source.is_file():
            continue
        dest = _STATIC_ICONS_DIR / source.name
        if not dest.is_file():
            shutil.copyfile(source, dest)


def load_presets() -> list[dict]:
    """Прочитать все пресеты приключений, отсортированные по имени файла."""
    presets = []
    for path in sorted(_DATA_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        icon = data.get("icon")
        icon_url = None
        if icon and (_STATIC_ICONS_DIR / icon).is_file():
            icon_url = f"/static/images/adventures/{icon}"
        presets.append(
            {
                "id": data["id"],
                "label": data.get("label", data["id"]),
                "description": data.get("description", ""),
                "goal_hint": data.get("goal_hint", ""),
                "icon_url": icon_url,
            }
        )
    return presets
