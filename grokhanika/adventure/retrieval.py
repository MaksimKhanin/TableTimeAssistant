"""Семантический поиск (RAG) по карточкам и лору + индексация эмбеддингов.

Заземляет ИИ-ГМ на данные из БД: вместо выдумывания NPC/лута/локаций ищем
наиболее близкие по смыслу существующие карточки и лор-записи. Векторы хранятся
в таблице ``embeddings`` (BLOB), близость считается косинусом (вектора
нормированы → скалярное произведение) брутфорсом по numpy — для десятков-сотен
карточек этого достаточно.

Та же таблица используется для эпизодической памяти приключения
(``entity_type="turn"``) — см. :mod:`grokhanika.adventure.memory`.
"""
from __future__ import annotations

import hashlib
from typing import Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Card, Embedding, LoreEntry
from ..enums import CardType
from . import config

# entity_type для карточек-сущностей и лор-записей
ENTITY_CARD = "card"
ENTITY_LORE = "lore"
ENTITY_TURN = "turn"


# ───────────────────────── текст сущности для эмбеддинга ─────────────────────────


def card_text(card: Card) -> str:
    """Текст карточки для векторизации: имя + описание (+ категория лора)."""
    parts = [card.name or ""]
    if isinstance(card, LoreEntry) and card.category:
        parts.append(f"[{card.category}]")
    if card.description:
        parts.append(card.description)
    return " — ".join(p for p in parts if p)


def _entity_type_for(card: Card) -> str:
    return ENTITY_LORE if isinstance(card, LoreEntry) else ENTITY_CARD


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _embed_model(session: Session, model_name: Optional[str]) -> str:
    return model_name or config.get_section(session, "embedder")["model"]


# ───────────────────────── индексация ─────────────────────────


def index_text(
    session: Session,
    entity_type: str,
    entity_id: int,
    text: str,
    *,
    model_name: str,
    commit: bool = True,
) -> Embedding:
    """Посчитать и сохранить вектор сущности (upsert; пропуск, если текст не менялся)."""
    from . import embeddings as emb  # ленивый импорт — не тянем torch без нужды

    text_hash = _hash(f"{model_name}:{text}")
    row = session.execute(
        select(Embedding).where(
            Embedding.entity_type == entity_type, Embedding.entity_id == entity_id
        )
    ).scalar_one_or_none()

    if row is not None and row.text_hash == text_hash and row.model == model_name:
        return row  # актуально — пересчёт не нужен

    vector = emb.embed_one(text, model_name, kind="passage")
    blob = emb.to_blob(vector)
    if row is None:
        row = Embedding(
            entity_type=entity_type,
            entity_id=entity_id,
            model=model_name,
            dim=int(vector.shape[0]),
            vector=blob,
            text_hash=text_hash,
        )
        session.add(row)
    else:
        row.model = model_name
        row.dim = int(vector.shape[0])
        row.vector = blob
        row.text_hash = text_hash
    if commit:
        session.commit()
    return row


def index_card(
    session: Session, card: Card, *, model_name: Optional[str] = None, commit: bool = True
) -> Optional[Embedding]:
    """Проиндексировать карточку (или лор-запись). Только осмысленные для приключения типы."""
    if card.id is None:
        return None
    model = _embed_model(session, model_name)
    return index_text(
        session,
        _entity_type_for(card),
        card.id,
        card_text(card),
        model_name=model,
        commit=commit,
    )


def remove_entity(session: Session, entity_type: str, entity_id: int, *, commit: bool = True) -> None:
    """Удалить эмбеддинг сущности (например, при удалении лор-записи)."""
    row = session.execute(
        select(Embedding).where(
            Embedding.entity_type == entity_type, Embedding.entity_id == entity_id
        )
    ).scalar_one_or_none()
    if row is not None:
        session.delete(row)
        if commit:
            session.commit()


# типы карточек, которые имеет смысл индексировать для приключения
_INDEXABLE_TYPES = {
    CardType.CHARACTER.value,
    CardType.CREATURE.value,
    CardType.ITEM.value,
    CardType.WEAPON.value,
    CardType.ARMOR.value,
    CardType.LORE.value,
}


def reindex(session: Session, *, model_name: Optional[str] = None) -> int:
    """Пересчитать эмбеддинги всех индексируемых карточек/лора. Возвращает их число."""
    model = _embed_model(session, model_name)
    cards = (
        session.execute(select(Card).where(Card.card_type.in_(_INDEXABLE_TYPES)))
        .scalars()
        .all()
    )
    count = 0
    for card in cards:
        index_card(session, card, model_name=model, commit=False)
        count += 1
    session.commit()
    return count


# ───────────────────────── поиск ─────────────────────────


def search_embeddings(
    session: Session,
    query_vector,
    *,
    entity_types: Sequence[str],
    top_k: int = 5,
    allowed_ids: Optional[Iterable[int]] = None,
) -> list[tuple[str, int, float]]:
    """Низкоуровневый поиск: вернуть ``[(entity_type, entity_id, score)]`` по убыванию.

    ``allowed_ids`` ограничивает кандидатов (например, ходами текущей сессии).
    """
    import numpy as np

    stmt = select(Embedding).where(Embedding.entity_type.in_(list(entity_types)))
    if allowed_ids is not None:
        allowed = list(allowed_ids)
        if not allowed:
            return []
        stmt = stmt.where(Embedding.entity_id.in_(allowed))
    rows = session.execute(stmt).scalars().all()
    if not rows:
        return []

    q = np.asarray(query_vector, dtype="float32")
    scored: list[tuple[str, int, float]] = []
    for row in rows:
        vec = np.frombuffer(row.vector, dtype="float32")
        if vec.shape != q.shape:
            continue  # другой эмбеддер/размерность — пропускаем
        scored.append((row.entity_type, row.entity_id, float(np.dot(q, vec))))
    scored.sort(key=lambda t: t[2], reverse=True)
    return scored[:top_k]


def semantic_search(
    session: Session,
    query: str,
    *,
    entity_types: Sequence[str] = (ENTITY_CARD, ENTITY_LORE),
    card_types: Optional[Sequence[str]] = None,
    top_k: int = 5,
    model_name: Optional[str] = None,
) -> list[dict]:
    """Найти карточки/лор, близкие к запросу. Возвращает ``[{card, score}]``.

    ``card_types`` дополнительно фильтрует по типу карточки (например, только
    существа/персонажи для NPC-сцены).
    """
    from . import embeddings as emb

    if not query.strip():
        return []
    model = _embed_model(session, model_name)
    qvec = emb.embed_one(query, model, kind="query")
    # берём с запасом — после гидрации может отсеяться по card_types
    hits = search_embeddings(session, qvec, entity_types=entity_types, top_k=top_k * 3)
    if not hits:
        return []

    ids = [eid for _etype, eid, _score in hits]
    cards = session.execute(select(Card).where(Card.id.in_(ids))).scalars().all()
    by_id = {c.id: c for c in cards}

    results: list[dict] = []
    allowed = set(card_types) if card_types else None
    for _etype, eid, score in hits:
        card = by_id.get(eid)
        if card is None:
            continue
        if allowed is not None and card.card_type not in allowed:
            continue
        results.append({"card": card, "score": score})
        if len(results) >= top_k:
            break
    return results
