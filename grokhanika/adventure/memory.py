"""Управление контекстом приключения: окно + компактинг + эпизодическая память.

Чтобы контекст не рос линейно и модель не деградировала:

* **скользящее окно** — в промт идут только последние N сообщений;
* **бегущая сводка (компактинг)** — выпавшие из окна ходы системная LLM сворачивает
  в ``running_summary`` (журнал кампании);
* **эпизодическая память (спилл)** — каждый ход эмбеддится в таблицу ``embeddings``
  (``entity_type="turn"``); по текущему сообщению поднимаем top-k релевантных
  прошлых ходов (semantic recall).

Все операции с эмбеддингами — best-effort: если эмбеддер недоступен, тихо
пропускаем (приключение продолжает работать без semantic recall).
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy.orm import Session

from ..db.models import AdventureMessage, AdventureSession
from .llm import LLMClient, LLMError

ROLE_LABELS = {"gm": "ГМ", "player": "Игрок", "system": "Система"}


def _label(msg: AdventureMessage) -> str:
    if msg.role == "player" and msg.speaker is not None:
        return msg.speaker.name
    return ROLE_LABELS.get(msg.role, msg.role)


def window(adv: AdventureSession, n: int) -> list[AdventureMessage]:
    """Последние ``n`` сообщений (скользящее окно)."""
    if n <= 0:
        return []
    return list(adv.messages[-n:])


def history_brief(adv: AdventureSession, n: int = 6) -> str:
    """Короткая выжимка последних ходов (для интент-анализа)."""
    lines = []
    for msg in window(adv, n):
        text = (msg.content or "").strip().replace("\n", " ")
        if len(text) > 200:
            text = text[:200] + "…"
        lines.append(f"{_label(msg)}: {text}")
    return "\n".join(lines)


# ───────────────────────── эпизодическая память (спилл/recall) ─────────────────────────


def record_turn(
    session: Session, adv: AdventureSession, message: AdventureMessage, *, model_name: str
) -> None:
    """Проиндексировать ход в вектор-память (best-effort)."""
    if not (message.content or "").strip():
        return
    try:
        from . import retrieval

        retrieval.index_text(
            session,
            retrieval.ENTITY_TURN,
            message.id,
            message.content,
            model_name=model_name,
            commit=False,
        )
    except Exception:  # noqa: BLE001 - память не должна ломать ход
        pass


def episodic_recall(
    session: Session,
    adv: AdventureSession,
    query: str,
    *,
    top_k: int,
    model_name: str,
    exclude_ids: Optional[Iterable[int]] = None,
) -> list[str]:
    """Поднять top-k релевантных прошлых ходов этой сессии. Best-effort → [] при сбое."""
    if not query.strip() or top_k <= 0:
        return []
    excluded = set(exclude_ids or ())
    allowed = [
        m.id for m in adv.messages if m.id not in excluded and m.role in ("gm", "player")
    ]
    if not allowed:
        return []
    try:
        from . import embeddings as emb
        from . import retrieval

        qvec = emb.embed_one(query, model_name, kind="query")
        hits = retrieval.search_embeddings(
            session, qvec, entity_types=[retrieval.ENTITY_TURN], top_k=top_k, allowed_ids=allowed
        )
    except Exception:  # noqa: BLE001
        return []

    by_id = {m.id: m for m in adv.messages}
    out: list[str] = []
    for _etype, mid, _score in hits:
        msg = by_id.get(mid)
        if msg is None:
            continue
        text = (msg.content or "").strip().replace("\n", " ")
        if len(text) > 300:
            text = text[:300] + "…"
        out.append(f"{_label(msg)}: {text}")
    return out


# ───────────────────────── компактинг (бегущая сводка) ─────────────────────────


def maybe_compact(
    session: Session, adv: AdventureSession, system_client: LLMClient, *, cfg: dict
) -> bool:
    """Свернуть выпавшие из окна ходы в ``running_summary``. True — если сворачивали.

    Best-effort: при недоступности системной LLM просто пропускаем (сводка не растёт,
    но окно + эпизодическая память продолжают работать).
    """
    window_n = int(cfg.get("window_messages", 16))
    threshold = int(cfg.get("compact_threshold", 24))
    msgs = list(adv.messages)
    if len(msgs) <= window_n:
        return False

    older = msgs[:-window_n]
    through = adv.summarized_through_message_id or 0
    to_summarize = [m for m in older if m.id > through]
    if len(to_summarize) < threshold:
        return False

    transcript = "\n".join(f"{_label(m)}: {(m.content or '').strip()}" for m in to_summarize)
    prev = adv.running_summary.strip()
    user = (
        "Ниже — журнал кампании (если есть) и новые ходы приключения. Обнови сжатую сводку: что "
        "произошло, ключевые решения партии, важные NPC/места/факты и статус главной цели. Пиши "
        "по-русски, компактно, без диалогов дословно. Верни только обновлённую сводку.\n\n"
        f"Текущая сводка:\n{prev or '(пусто)'}\n\n"
        f"Новые ходы:\n{transcript}"
    )
    messages = [
        {"role": "system", "content": "Ты ведёшь краткий журнал кампании настольной RPG."},
        {"role": "user", "content": user},
    ]
    try:
        summary = system_client.chat(messages, temperature=0.2)
    except LLMError:
        return False

    adv.running_summary = summary.strip()
    adv.summarized_through_message_id = max(m.id for m in to_summarize)
    session.flush()
    return True
