"""Наполнение БД сид-данными.

Каталог (оружие, броня, предметы, персонажи, существа, лор) полностью описан
в YAML-файлах ``grokhanika/data/catalog/`` — см. :mod:`grokhanika.db.yaml_loader`.
Здесь только оркестрация: построить объекты, сохранить в БД, подхватить
готовые изображения из ``grokhanika/data/images/``.
"""
from __future__ import annotations

from .yaml_loader import load_catalog, sync_pregenerated_images


def seed_all(session) -> dict:
    """Наполнить БД и вернуть словарь ключ→карточка."""
    cat = load_catalog()
    session.add_all(list(cat.values()))
    session.commit()
    sync_pregenerated_images(cat)
    session.commit()
    return cat
