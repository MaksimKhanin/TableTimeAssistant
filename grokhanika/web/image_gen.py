"""Генерация арта карточек (OpenAI-совместимый ``/images/generations``).

Настройки (эндпоинт/модель/ключ/размер + стилевой промт) хранятся в
``app_settings`` (ключ ``image_gen``), правятся через фронтенд — по тому же
принципу, что и конфиг LLM в :mod:`grokhanika.adventure.config`, но независимо
от него: генерация арта — функция админки, а не приключения.

Промт запроса = описание карточки + ``style_prompt`` (единая стилистика для
всего арта, задаётся один раз в настройках).
"""
from __future__ import annotations

import base64
import copy
import os
import time
from typing import Optional

from sqlalchemy.orm import Session

from ..db.models import AppSetting, Card

_SETTINGS_KEY = "image_gen"
_STATIC_IMAGES_ROOT = os.path.join(os.path.dirname(__file__), "static", "images", "cards")


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def _defaults() -> dict:
    return {
        "base_url": _env("GROKHANIKA_IMAGE_BASE_URL", default="https://api.openai.com/v1"),
        "model": _env("GROKHANIKA_IMAGE_MODEL", default="dall-e-3"),
        "api_key": _env("GROKHANIKA_IMAGE_API_KEY", default=""),
        "size": _env("GROKHANIKA_IMAGE_SIZE", default="1024x1024"),
        "style_prompt": _env(
            "GROKHANIKA_IMAGE_STYLE_PROMPT",
            default=(
                "Иллюстрация карточки настольной ролевой игры: детализированный "
                "фэнтезийный арт, единая художественная стилистика, портрет по пояс "
                "на нейтральном фоне, без текста и рамок на изображении."
            ),
        ),
    }


# ───────────────────────── настройки (app_settings) ─────────────────────────


def get_config(session: Session) -> dict:
    """Слитый конфиг: дефолт ⊕ сохранённое в БД."""
    row = session.get(AppSetting, _SETTINGS_KEY)
    cfg = copy.deepcopy(_defaults())
    if row and row.value:
        cfg.update(row.value)
    return cfg


def save_config(session: Session, payload: dict) -> dict:
    """Upsert настроек генерации изображений. Возвращает новый конфиг."""
    row = session.get(AppSetting, _SETTINGS_KEY)
    if row is None:
        session.add(AppSetting(key=_SETTINGS_KEY, value=payload))
    else:
        row.value = {**(row.value or {}), **payload}
    session.commit()
    return get_config(session)


def build_prompt(description: str, style_prompt: str) -> str:
    """Промт генерации: описание карточки + стилевая приписка из настроек."""
    parts = [p.strip() for p in (description or "", style_prompt or "") if p and p.strip()]
    return "\n\n".join(parts)


# ───────────────────────── клиент ─────────────────────────


class ImageGenError(RuntimeError):
    """Ошибка обращения к серверу генерации изображений."""


class ImageGenClient:
    """Тонкая обёртка над OpenAI-совместимым ``POST {base_url}/images/generations``."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str = "",
        size: str = "1024x1024",
        timeout: float = 120.0,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.model = model
        self.api_key = api_key or ""
        self.size = size or "1024x1024"
        self.timeout = timeout

    def _client(self):
        import httpx

        # trust_env=False — не использовать HTTP(S)_PROXY для локального сервера
        return httpx.Client(timeout=self.timeout, trust_env=False)

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def generate(self, prompt: str) -> bytes:
        """Сгенерировать изображение по промту. Возвращает PNG-байты."""
        if not self.base_url:
            raise ImageGenError("не задан base_url модели изображений")
        body = {
            "model": self.model,
            "prompt": prompt,
            "size": self.size,
            "response_format": "b64_json",
            "n": 1,
        }
        try:
            with self._client() as client:
                resp = client.post(
                    f"{self.base_url}/images/generations", headers=self._headers(), json=body
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # httpx/JSON/сеть
            raise ImageGenError(f"генерация изображения не удалась: {exc}") from exc
        try:
            b64 = data["data"][0]["b64_json"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ImageGenError(f"неожиданный формат ответа: {data!r}") from exc
        try:
            return base64.b64decode(b64)
        except Exception as exc:
            raise ImageGenError(f"не удалось декодировать изображение: {exc}") from exc

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


def client_for(session: Session) -> ImageGenClient:
    """Собрать клиент из сохранённого конфига."""
    cfg = get_config(session)
    return ImageGenClient(
        base_url=cfg.get("base_url", ""),
        model=cfg.get("model", ""),
        api_key=cfg.get("api_key", ""),
        size=cfg.get("size", "1024x1024"),
    )


# ───────────────────────── сохранение файла ─────────────────────────


def save_image(card: Card, image_bytes: bytes) -> str:
    """Сохранить PNG на диск, вернуть новый ``image_id`` (``<тип>/<файл>.png``).

    Имя файла включает таймстамп, чтобы каждая перегенерация давала свежий URL
    (иначе браузер показывал бы закэшированный старый арт по тому же пути).
    Прежний файл карточки удаляется, чтобы не копить версии на диске.
    """
    subdir = os.path.join(_STATIC_IMAGES_ROOT, card.card_type)
    os.makedirs(subdir, exist_ok=True)

    if card.image_id:
        old_path = os.path.join(_STATIC_IMAGES_ROOT, card.image_id.replace("/", os.sep))
        if os.path.isfile(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    filename = f"{card.card_type}_{card.id}_{int(time.time())}.png"
    with open(os.path.join(subdir, filename), "wb") as f:
        f.write(image_bytes)
    return f"{card.card_type}/{filename}"
