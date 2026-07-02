"""Мост между намерением игрока (интент-анализ) и боевым движком.

Подбирает карточки противников из каталога по RAG-запросу системной LLM —
единственная новая бизнес-логика моста. Сам бой ведётся существующим
``web.simulation`` (``start_interactive``/``submit_action``) поверх ``engine.combat`` —
здесь ничего не дублируется.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import AdventureSession, Card
from ..enums import CardType
from .intent import Intent

_ENEMY_CARD_TYPES = (CardType.CREATURE.value, CardType.CHARACTER.value)
_DEFAULT_ENEMY_COUNT = 2
_MIN_ENEMIES = 1
_MAX_ENEMIES = 6


def select_enemies(session: Session, adv: AdventureSession, intent: Intent) -> list[Card]:
    """Подобрать карточки противников для намерения ``combat_initiation``.

    RAG-поиск (``retrieval.semantic_search``) по ``intent.enemy_query`` с фолбэком на
    общие ``search_queries`` интента, если системная LLM не указала запрос отдельно.
    Игровые персонажи партии исключаются. При недоступном эмбеддере/пустом каталоге —
    безопасный пустой результат (бой не стартует, см. ``prompts.enrichment_for``).
    """
    try:
        from . import retrieval
    except Exception:  # noqa: BLE001 - модуль приключения/эмбеддер недоступны
        return []

    query = intent.enemy_query.strip() or " ".join(intent.search_queries).strip()
    if not query:
        return []

    count = intent.enemy_count if intent.enemy_count > 0 else _DEFAULT_ENEMY_COUNT
    count = max(_MIN_ENEMIES, min(count, _MAX_ENEMIES, 2 * max(len(adv.party), 1)))

    try:
        hits = retrieval.semantic_search(
            session, query, card_types=list(_ENEMY_CARD_TYPES), top_k=count * 2
        )
    except Exception:  # noqa: BLE001 - эмбеддер недоступен → без боя, только нарратив
        return []

    party_ids = {c.id for c in adv.party}
    candidates: list[Card] = []
    seen: set[int] = set()
    for hit in hits:
        card = hit["card"]
        if card.id in seen or card.id in party_ids or getattr(card, "is_player", False):
            continue
        seen.add(card.id)
        candidates.append(card)
        if len(candidates) >= count:
            break
    return candidates
