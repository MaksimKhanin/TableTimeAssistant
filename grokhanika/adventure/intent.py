"""Анализ намерений игрока перед ответом ГМ.

Системная LLM в JSON-режиме классифицирует последнюю реплику игрока: тип
намерения, нужен ли бросок, начинается ли бой, покидает ли игрок локацию, куда
именно (свободным текстом, не карточкой каталога) и какие NPC с каким
количеством появляются в кадре. Результат управляет зачисткой/обновлением сцены
и дообогащением промта ГМ. Температура 0 — при одинаковом вводе модель должна
стабильно возвращать одинаковый результат (детерминированность сцены). При
сбое разбора — безопасный дефолт «диалог», без смены локации/NPC.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from .llm import LLMClient, LLMError
from .prompts import (
    INTENT_TYPES,
    intent_system_prompt,
    intent_user_prompt,
    opening_system_prompt,
    opening_user_prompt,
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_MAX_NPC_MENTIONS = 6
_MAX_MENTION_COUNT = 8


@dataclass
class Intent:
    intent_type: str = "dialogue"
    requires_roll: bool = False
    roll_type: str = ""
    roll_difficulty: int = 0
    combat_initiation: bool = False
    leaves_location: bool = False
    location_name: str = ""
    location_description: str = ""
    npc_mentions: list[dict] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    enemy_query: str = ""
    enemy_count: int = 0

    def to_dict(self) -> dict:
        return {
            "intent_type": self.intent_type,
            "requires_roll": self.requires_roll,
            "roll_type": self.roll_type,
            "roll_difficulty": self.roll_difficulty,
            "combat_initiation": self.combat_initiation,
            "leaves_location": self.leaves_location,
            "location_name": self.location_name,
            "location_description": self.location_description,
            "npc_mentions": [dict(m) for m in self.npc_mentions],
            "search_queries": list(self.search_queries),
            "enemy_query": self.enemy_query,
            "enemy_count": self.enemy_count,
        }


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "да", "yes")
    return bool(value)


def _as_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_npc_mentions(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    mentions: list[dict] = []
    for item in value[:_MAX_NPC_MENTIONS]:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query", "")).strip()
        if not query:
            continue
        count = max(1, min(_as_int(item.get("count")) or 1, _MAX_MENTION_COUNT))
        mentions.append({"query": query, "count": count})
    return mentions


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
        roll_difficulty=max(0, min(_as_int(data.get("roll_difficulty")), 30)),
        combat_initiation=_as_bool(data.get("combat_initiation")),
        leaves_location=_as_bool(data.get("leaves_location")),
        location_name=str(data.get("location_name", "")).strip(),
        location_description=str(data.get("location_description", "")).strip(),
        npc_mentions=_as_npc_mentions(data.get("npc_mentions")),
        search_queries=queries,
        enemy_query=str(data.get("enemy_query", "")).strip(),
        enemy_count=_as_int(data.get("enemy_count")),
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


def analyze_opening(client: LLMClient, description: str, goal: str) -> Intent:
    """Определить стартовую локацию/NPC приключения по завязке и цели (для вводной ГМ).

    Использует ту же JSON-схему и парсер, что и обычный интент-анализ, но с
    отдельным промтом: на старте ещё нет реплики игрока, только завязка.
    """
    messages = [
        {"role": "system", "content": opening_system_prompt()},
        {"role": "user", "content": opening_user_prompt(description, goal)},
    ]
    try:
        raw = client.chat(messages, json_mode=True, temperature=0.0)
    except LLMError:
        return Intent()
    return parse_intent(raw)
