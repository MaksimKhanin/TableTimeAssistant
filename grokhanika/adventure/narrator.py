"""Сборка сообщений для ИИ-ГМ и потоковая генерация ответа.

Персона ГМ (стабильный префикс) и динамический контекст хода кладутся в одно
ведущее system-сообщение (надёжнее для локальных моделей, часть которых учитывает
только первый system), далее — окно диалога, затем текущая реплика игрока.
"""
from __future__ import annotations

from typing import Iterator, Optional, Sequence

from ..db.models import AdventureMessage, AdventureSession
from .llm import LLMClient


def build_messages(
    adv: AdventureSession,
    context_block: str,
    window_msgs: Sequence[AdventureMessage],
    *,
    kickoff: Optional[str] = None,
) -> list[dict]:
    """Собрать messages для chat-completions."""
    system = adv.system_prompt
    if context_block.strip():
        system = f"{system}\n\n{context_block}"
    messages: list[dict] = [{"role": "system", "content": system}]

    for msg in window_msgs:
        if msg.role == "gm":
            messages.append({"role": "assistant", "content": msg.content})
        elif msg.role == "player":
            name = msg.speaker.name if msg.speaker is not None else "Игрок"
            messages.append({"role": "user", "content": f"[{name}]: {msg.content}"})
        else:  # системное событие
            messages.append({"role": "user", "content": f"(событие) {msg.content}"})

    if kickoff:
        messages.append({"role": "user", "content": kickoff})
    # модель отвечает на реплику пользователя — последний ход должен быть user
    if messages[-1]["role"] != "user":
        messages.append({"role": "user", "content": "Продолжай повествование как ГМ."})
    return messages


def stream(client: LLMClient, messages: list[dict]) -> Iterator[str]:
    """Потоковая генерация ответа ГМ (дельты текста)."""
    yield from client.stream(messages)
