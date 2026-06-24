"""Симуляция боя для UI: прогон энкаунтера с записью пошаговых событий.

``RecordingEncounter`` — тонкая надстройка над :class:`~grokhanika.engine.Encounter`,
которая после каждого действия снимает **снимок состояния всех участников** и
новые строки лога. Получается поток событий вида «раунд → действие → HP всех» —
ровно то, что будущий анимированный фронтенд проигрывает покадрово (твины HP-баров,
всплытие урона и т.п.). Сам движок при этом не меняется.
"""
from __future__ import annotations

import random
from typing import Optional

from sqlalchemy.orm import Session

from ..db.models import Card, Character, Creature
from ..engine import Combat, Combatant, Encounter, SimpleAIController

ALLY_SIDE = "party"
ENEMY_SIDE = "enemy"


class RecordingEncounter(Encounter):
    """Энкаунтер, пишущий пошаговые события боя в ``self.events``."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.events: list[dict] = []
        self._logged = 0

    def _snapshot(self, *, phase: str, actor_uid: Optional[int]) -> None:
        new_lines = self.combat.log[self._logged:]
        self._logged = len(self.combat.log)
        self.events.append({
            "round": self.combat.round + 1,  # раунд, который сейчас идёт (1-based)
            "phase": phase,
            "actor_uid": actor_uid,
            "log": list(new_lines),
            "combatants": [self._combatant_state(c) for c in self.combat.combatants],
        })

    @staticmethod
    def _combatant_state(c: Combatant) -> dict:
        return {
            "uid": c.uid,
            "name": c.name,
            "side": c.side,
            "kind": c.kind,
            "hp": max(0, c.current_hp),
            "max_hp": c.max_hp,
            "alive": c.in_combat,
            "dying": c.is_dying,
        }

    # ── перехват жизненного цикла ──

    def start(self) -> None:
        super().start()
        self._snapshot(phase="start", actor_uid=None)

    def _apply(self, action, actor) -> None:
        super()._apply(action, actor)
        self._snapshot(phase="action", actor_uid=actor.uid)


# ───────────────────────── сборка ростера ─────────────────────────


def _load_combatants(session: Session, ids: list[int], side: str) -> list[Combatant]:
    combatants: list[Combatant] = []
    for card_id in ids:
        card = session.get(Card, card_id)
        if card is None:
            raise ValueError(f"карточка id={card_id} не найдена")
        if not isinstance(card, (Character, Creature)):
            raise ValueError(f"«{card.name}» нельзя поставить в бой — это не персонаж/существо")
        combatants.append(Combatant(card, side))
    return combatants


def run_simulation(
    session: Session,
    ally_ids: list[int],
    enemy_ids: list[int],
    *,
    seed: Optional[int] = None,
    max_rounds: int = 50,
) -> dict:
    """Прогнать автобой союзников против врагов и вернуть события + итог.

    За обе стороны (включая союзных NPC) играет компьютер (``SimpleAIController``).
    """
    if not ally_ids or not enemy_ids:
        raise ValueError("нужны участники с обеих сторон")

    rng = random.Random(seed)
    allies = _load_combatants(session, ally_ids, ALLY_SIDE)
    enemies = _load_combatants(session, enemy_ids, ENEMY_SIDE)

    combat = Combat(allies + enemies, rng=rng, session=session)
    encounter = RecordingEncounter(
        combat,
        controllers={ALLY_SIDE: SimpleAIController(), ENEMY_SIDE: SimpleAIController()},
        max_rounds=max_rounds,
    )
    outcome = encounter.run()

    side_label = {ALLY_SIDE: "Союзники", ENEMY_SIDE: "Враги"}
    return {
        "seed": seed,
        "sides": side_label,
        "roster": {
            ALLY_SIDE: [c.name for c in allies],
            ENEMY_SIDE: [c.name for c in enemies],
        },
        "events": encounter.events,
        "outcome": {
            "winner": outcome.winner,
            "winner_label": side_label.get(outcome.winner) if outcome.winner else None,
            "rounds": outcome.rounds,
            "ended_by": outcome.ended_by,
            "survivors": outcome.survivors,
            "log": outcome.log,
        },
    }
