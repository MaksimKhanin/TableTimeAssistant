"""Конфигурация LLM/эмбеддера приключения.

Источник истины — таблица ``app_settings`` в БД (правится через фронтенд). При
отсутствии ключа берём дефолт из переменной окружения, затем — встроенный
дефолт. Так пользователь может на лету менять эндпоинты/модели без перезапуска.

Секции конфига:

* ``narrator`` — LLM-повествователь (ГМ): ``base_url``, ``model``, ``api_key``,
  ``temperature``, ``top_p``, ``top_k``, ``max_tokens``, ``reasoning_effort``,
  ``response_format``;
* ``system``   — системная LLM (интент-анализ, компактинг) — те же поля;
* ``embedder`` — модель sentence-transformers (``model``);
* ``memory``   — пороги управления контекстом.

``base_url`` указывает на OpenAI-совместимый эндпоинт (Ollama: ``/v1``, vLLM:
``/v1`` и т.п.); клиент бьёт в ``{base_url}/chat/completions``.
"""
from __future__ import annotations

import copy
import os
from typing import Any, Optional

from sqlalchemy.orm import Session

# секции конфига, которые UI может читать/писать
SECTIONS = ("narrator", "system", "embedder", "memory")


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def _defaults() -> dict[str, dict[str, Any]]:
    """Встроенные дефолты с учётом переменных окружения.

    По умолчанию указан провайдер GenAPI (OpenAI-совместимый прокси
    ``https://proxy.gen-api.ru/v1``, модель ``qwen-3-6-plus``) с параметрами
    генерации из его документации.
    """
    common_url = _env("GROKHANIKA_LLM_BASE_URL", default="https://proxy.gen-api.ru/v1")
    common_model = _env("GROKHANIKA_LLM_MODEL", default="qwen-3-6-plus")
    common_key = _env("GROKHANIKA_LLM_API_KEY", default="")
    gen_params = {
        "temperature": 1,
        "top_p": 1,
        "top_k": 0,
        "max_tokens": 65536,
        "reasoning_effort": "none",
        "response_format": "text",
    }
    return {
        "narrator": {
            "base_url": _env("GROKHANIKA_NARRATOR_BASE_URL", default=common_url),
            "model": _env("GROKHANIKA_NARRATOR_MODEL", default=common_model),
            "api_key": _env("GROKHANIKA_NARRATOR_API_KEY", default=common_key),
            **gen_params,
        },
        "system": {
            "base_url": _env("GROKHANIKA_SYSTEM_BASE_URL", default=common_url),
            "model": _env("GROKHANIKA_SYSTEM_MODEL", default=common_model),
            "api_key": _env("GROKHANIKA_SYSTEM_API_KEY", default=common_key),
            **gen_params,
        },
        "embedder": {
            "model": _env("GROKHANIKA_EMBED_MODEL", default="intfloat/multilingual-e5-base"),
        },
        "memory": {
            "window_messages": 16,     # сколько последних сообщений идёт дословно
            "compact_threshold": 24,   # при превышении — свернуть «выпавшие» в сводку
            "episodic_top_k": 4,       # сколько прошлых ходов поднимать из вектор-памяти
            "retrieval_top_k": 5,      # сколько карточек/лора поднимать RAG-поиском
            "retrieval_min_score": 0.5,  # мин. косинусное сходство — отсекает случайные совпадения
        },
    }


def _merge(base: dict, override: Optional[dict]) -> dict:
    out = copy.deepcopy(base)
    if override:
        for key, value in override.items():
            out[key] = value
    return out


# ───────────────────────── чтение/запись ─────────────────────────


def _stored(session: Session) -> dict[str, dict]:
    """Все сохранённые секции из app_settings (ключ → JSON-значение)."""
    from ..db.models import AppSetting  # локальный импорт — избегаем цикла

    rows = session.query(AppSetting).filter(AppSetting.key.in_(SECTIONS)).all()
    return {row.key: (row.value or {}) for row in rows}


def get_section(session: Session, key: str) -> dict:
    """Слитый конфиг секции: дефолт ⊕ сохранённое в БД."""
    if key not in SECTIONS:
        raise KeyError(f"неизвестная секция конфига: {key!r}")
    defaults = _defaults()[key]
    stored = _stored(session).get(key)
    return _merge(defaults, stored)


def get_all(session: Session) -> dict[str, dict]:
    """Полный конфиг по всем секциям (для фронтенда)."""
    return {key: get_section(session, key) for key in SECTIONS}


def save_sections(session: Session, payload: dict[str, dict]) -> dict[str, dict]:
    """Upsert переданных секций. Лишние ключи игнорируются. Возвращает новый конфиг."""
    from ..db.models import AppSetting

    for key, value in payload.items():
        if key not in SECTIONS or not isinstance(value, dict):
            continue
        row = session.get(AppSetting, key)
        if row is None:
            session.add(AppSetting(key=key, value=value))
        else:
            # сливаем с уже сохранённым, чтобы частичный апдейт не затирал поля
            merged = _merge(row.value or {}, value)
            row.value = merged
    session.commit()
    return get_all(session)
