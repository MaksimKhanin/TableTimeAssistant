"""Анализ намерений игрока перед ответом ГМ.

Системная LLM в JSON-режиме классифицирует последнюю реплику игрока: тип
намерения, нужен ли бросок, начинается ли бой, покидает ли игрок локацию, и какие
сущности искать в базе (для RAG). Результат управляет зачисткой сцены, поиском и
дообогащением промта ГМ. При сбое разбора — безопасный дефолт «диалог».
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from .llm import LLMClient, LLMError
from .prompts import INTENT_TYPES, intent_system_prompt, intent_user_prompt

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class Intent:
    intent_type: str = "dialogue"
    requires_roll: bool = False
    roll_type: str = ""
    combat_initiation: bool = False
    leaves_location: bool = False
    search_queries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "intent_type": self.intent_type,
            "requires_roll": self.requires_roll,
            "roll_type": self.roll_type,
            "combat_initiation": self.combat_initiation,
            "leaves_location": self.leaves_location,
            "search_queries": list(self.search_queries),
        }


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "да", "yes")
    return bool(value)


def parse_intent(raw: str) -> Intent:
    """Распарсить JSON-ответ модели в :class:`Intent` (устойчиво к мусору вокруг)."""
    if not raw:
        return Intent()
    text = raw.strip()
    data: Optional[dict] = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_RE.search(text)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = None
    if not isinstance(data, dict):
        return Intent()

    intent_type = str(data.get("intent_type", "dialogue")).strip().lower()
    if intent_type not in INTENT_TYPES:
        intent_type = "dialogue"

    queries = data.get("search_queries") or []
    if isinstance(queries, str):
        queries = [queries]
    queries = [str(q).strip() for q in queries if str(q).strip()][:4]

    return Intent(
        intent_type=intent_type,
        requires_roll=_as_bool(data.get("requires_roll")),
        roll_type=str(data.get("roll_type", "")).strip(),
        combat_initiation=_as_bool(data.get("combat_initiation")),
        leaves_location=_as_bool(data.get("leaves_location")),
        search_queries=queries,
    )


def analyze_intent(
    client: LLMClient, history_brief: str, character_name: str, text: str
) -> Intent:
    """Запросить интент-анализ у системной LLM. На сбой — безопасный дефолт."""
    messages = [
        {"role": "system", "content": intent_system_prompt()},
        {"role": "user", "content": intent_user_prompt(history_brief, character_name, text)},
    ]
    try:
        raw = client.chat(messages, json_mode=True, temperature=0.0)
    except LLMError:
        # LLM недоступна — не блокируем ход, считаем намерение диалогом и ищем по тексту
        fallback = Intent(search_queries=[text[:80]] if text.strip() else [])
        return fallback
    return parse_intent(raw)
