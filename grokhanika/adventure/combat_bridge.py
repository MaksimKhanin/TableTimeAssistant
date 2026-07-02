"""Подбор противников для боя из каталога существ/персонажей по интенту (RAG).

Сам бой ведёт ``web.simulation`` поверх ``engine.combat`` (см. ``session.py``) —
этот модуль только находит подходящую карточку-противника по
``intent.enemy_query`` и разворачивает её в список нужной длины
(``intent.enemy_count``): бой ждёт ``enemy_ids`` как список id по одному на
участника, повтор id — это несколько экземпляров одной и той же карточки.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import AdventureSession, Card
from ..enums import CardType
from .intent import Intent

_ENEMY_TYPES = (CardType.CREATURE.value, CardType.CHARACTER.value)
_MAX_ENEMIES = 8


def select_enemies(session: Session, adv: AdventureSession, intent: Intent) -> list[Card]:
    """Найти карточку противника по интенту и повторить её под ``enemy_count``.

    Возвращает пустой список, если запрос пуст или ничего похожего не нашлось
    (в этом случае бой не начинается — см. ``prompts.enrichment_for``).
    """
    query = intent.enemy_query.strip()
    if not query:
        return []
    from . import retrieval

    hits = retrieval.semantic_search(session, query, card_types=_ENEMY_TYPES, top_k=5)
    card = next((h["card"] for h in hits if not getattr(h["card"], "is_player", False)), None)
    if card is None:
        return []
    count = max(1, min(intent.enemy_count or 1, _MAX_ENEMIES))
    return [card] * count
