"""Клиент к локальному OpenAI-совместимому LLM-серверу (Ollama/vLLM/llama.cpp/...).

Работает поверх ``POST {base_url}/chat/completions``. Поддерживает обычный и
потоковый (SSE) режим, а также JSON-режим (``response_format``) для интент-анализа.
Две роли (нарратор и системная LLM) инстанцируются из конфига независимо — это
могут быть разные модели/эндпоинты.

``httpx`` создаётся с ``trust_env=False``: локальный LLM-сервер не должен ходить
через корпоративный прокси из переменных окружения.
"""
from __future__ import annotations

import json
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from . import config

# ``[DONE]``-маркер конца SSE-потока OpenAI-совместимого API
_SSE_DONE = "[DONE]"


class LLMError(RuntimeError):
    """Ошибка обращения к LLM-серверу (сеть/HTTP/формат)."""


class LLMClient:
    """Тонкая обёртка над одним эндпоинтом chat-completions."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str = "",
        temperature: Optional[float] = None,
        timeout: float = 180.0,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.model = model
        self.api_key = api_key or ""
        self.temperature = temperature
        self.timeout = timeout

    # ── внутреннее ──

    def _client(self):
        import httpx

        # trust_env=False — не использовать HTTP(S)_PROXY для локального сервера
        return httpx.Client(timeout=self.timeout, trust_env=False)

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _body(
        self,
        messages: list[dict],
        *,
        stream: bool,
        json_mode: bool,
        temperature: Optional[float],
    ) -> dict:
        body: dict = {"model": self.model, "messages": messages, "stream": stream}
        temp = temperature if temperature is not None else self.temperature
        if temp is not None:
            body["temperature"] = temp
        if json_mode:
            # OpenAI-совместимый JSON-режим; для надёжности дублируется инструкцией в промте
            body["response_format"] = {"type": "json_object"}
        return body

    # ── публичное API ──

    def chat(
        self,
        messages: list[dict],
        *,
        temperature: Optional[float] = None,
        json_mode: bool = False,
    ) -> str:
        """Синхронный ответ целиком (для интент-анализа и компактинга)."""
        body = self._body(messages, stream=False, json_mode=json_mode, temperature=temperature)
        try:
            with self._client() as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions", headers=self._headers(), json=body
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # httpx/JSON/сеть
            raise LLMError(f"LLM chat failed: {exc}") from exc
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected LLM response shape: {data!r}") from exc

    def stream(
        self,
        messages: list[dict],
        *,
        temperature: Optional[float] = None,
    ) -> Iterator[str]:
        """Потоковая генерация: отдаёт дельты текста по мере поступления."""
        body = self._body(messages, stream=True, json_mode=False, temperature=temperature)
        try:
            with self._client() as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=body,
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        delta = _parse_sse_delta(line)
                        if delta:
                            yield delta
        except Exception as exc:
            raise LLMError(f"LLM stream failed: {exc}") from exc

    def health_check(self) -> dict:
        """Пинг эндпоинта (для кнопки «Проверить» в настройках)."""
        if not self.base_url:
            return {"ok": False, "error": "не задан base_url"}
        try:
            with self._client() as client:
                resp = client.get(f"{self.base_url}/models", headers=self._headers())
            return {"ok": resp.status_code < 500, "status": resp.status_code, "model": self.model}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "model": self.model}


def _parse_sse_delta(line: str) -> Optional[str]:
    """Достать ``choices[0].delta.content`` из одной SSE-строки, либо None."""
    if not line:
        return None
    if line.startswith("data:"):
        payload = line[len("data:"):].strip()
        if not payload or payload == _SSE_DONE:
            return None
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            return None
        choices = chunk.get("choices") or [{}]
        delta = (choices[0].get("delta") or {}).get("content")
        return delta or None
    return None


# ───────────────────────── фабрика по роли ─────────────────────────


def client_for(session: Session, role: str) -> LLMClient:
    """Собрать клиент для роли ``narrator`` или ``system`` из конфига в БД."""
    if role not in ("narrator", "system"):
        raise ValueError(f"неизвестная роль LLM: {role!r}")
    cfg = config.get_section(session, role)
    return LLMClient(
        base_url=cfg.get("base_url", ""),
        model=cfg.get("model", ""),
        api_key=cfg.get("api_key", ""),
        temperature=cfg.get("temperature"),
    )
