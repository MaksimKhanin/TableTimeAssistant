"""Локальный эмбеддер на sentence-transformers (HuggingFace).

Модель грузится лениво и кешируется по имени (singleton на процесс), потому что
загрузка весов дорогая. Для семейства e5 добавляем префиксы ``query:`` /
``passage:`` — без них качество заметно падает.

Тесты не должны тянуть torch: мокайте :func:`embed` (или подменяйте
``_load_model``) детерминированными векторами.
"""
from __future__ import annotations

import threading
from typing import Sequence

import numpy as np

_LOCK = threading.Lock()
_MODELS: dict[str, object] = {}


def _load_model(model_name: str):
    """Загрузить (и закешировать) модель sentence-transformers."""
    model = _MODELS.get(model_name)
    if model is None:
        with _LOCK:
            model = _MODELS.get(model_name)
            if model is None:
                from sentence_transformers import SentenceTransformer

                model = SentenceTransformer(model_name)
                _MODELS[model_name] = model
    return model


def _with_prefix(texts: Sequence[str], model_name: str, kind: str) -> list[str]:
    """Префикс query/passage для e5-моделей; иначе текст как есть."""
    if "e5" in model_name.lower():
        prefix = "query: " if kind == "query" else "passage: "
        return [f"{prefix}{t}" for t in texts]
    return list(texts)


def embed(texts: Sequence[str], model_name: str, *, kind: str = "passage") -> np.ndarray:
    """Векторизовать тексты. ``kind`` ∈ {``passage``, ``query``}.

    Возвращает массив ``float32`` формы ``(len(texts), dim)`` с L2-нормировкой
    (косинус сводится к скалярному произведению).
    """
    if not texts:
        return np.zeros((0, 0), dtype="float32")
    prepared = _with_prefix(texts, model_name, kind)
    model = _load_model(model_name)
    vectors = model.encode(prepared, normalize_embeddings=True, convert_to_numpy=True)
    return np.asarray(vectors, dtype="float32")


def embed_one(text: str, model_name: str, *, kind: str = "passage") -> np.ndarray:
    """Векторизовать один текст → 1-D массив ``float32``."""
    return embed([text], model_name, kind=kind)[0]


def to_blob(vector: np.ndarray) -> bytes:
    """Сериализовать вектор в bytes для хранения в SQLite (BLOB)."""
    return np.asarray(vector, dtype="float32").tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    """Десериализовать вектор из BLOB."""
    return np.frombuffer(blob, dtype="float32")
