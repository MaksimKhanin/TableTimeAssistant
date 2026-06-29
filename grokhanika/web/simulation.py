"""Симуляция боя для UI: автобой и интерактивный режим с паузами на ходы игрока.

``RecordingEncounter`` — надстройка над :class:`~grokhanika.engine.Encounter`,
снимающая пошаговые события. ``InteractiveEncounter`` — дополнительный слой:
делает ходы ИИ, пока не дойдёт до хода игрока, и возвращает состояние с
доступными действиями для выбора через UI.
"""
from __future__ import annotations

import random
import uuid as _uuid
from typing import Optional

from sqlalchemy.orm import Session

from ..db.models import Card, Character, Creature
from ..engine import Combat, Combatant, Encounter, SimpleAIController
from ..engine.actions import Action, ActionKind
from ..enums import AbilityTrigger

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
            "round": self.combat.round + 1,
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
            "description": c.description,
            "side": c.side,
            "kind": c.kind,
            "hp": max(0, c.current_hp),
            "max_hp": c.max_hp,
            "alive": c.in_combat,
            "dying": c.is_dying,
            "has_bastion": c.has_bastion,
            "phys_def": c.phys_defense,
            "mag_def": c.mag_defense,
            "mental_def": c.mental_defense,
            "effects": [
                {
                    "target": e.target,
                    "target_type": e.target_type,
                    "modifier": e.modifier,
                    "duration": e.duration,
                    "source_type": e.source_type,
                    "description": e.description,
                }
                for e in c.active_effects
            ],
        }

    def start(self) -> None:
        super().start()
        self._snapshot(phase="start", actor_uid=None)

    def _apply(self, action, actor) -> None:
        super()._apply(action, actor)
        self._snapshot(phase="action", actor_uid=actor.uid)


# ───────────────────────── интерактивный режим ─────────────────────────


class InteractiveEncounter(RecordingEncounter):
    """Энкаунтер с паузами на ходы игрока.

    Ходит ИИ за всех неигровых участников, пока не придёт очередь
    кого-то из стороны ``player_side``. Тогда возвращает состояние
    «waiting» с доступными действиями для актора. Игрок выбирает
    действие и вызывает ``submit(action)`` — цикл продолжается.
    """

    def __init__(self, *args, player_side: str = ALLY_SIDE, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.player_side = player_side
        self._queue: list[Combatant] = []
        self._round_active: bool = False
        self._waiting_uid: Optional[int] = None
        self._last_sent: int = 0

    # ── публичный API ──

    def begin(self) -> dict:
        """Запустить бой и дойти до первого хода игрока."""
        self.start()
        return self._advance(None)

    def submit(self, action: Action) -> dict:
        """Принять действие игрока и продвинуть бой до следующего хода игрока."""
        return self._advance(action)

    # ── внутренний цикл ──

    def _advance(self, action: Optional[Action]) -> dict:
        combat = self.combat

        # Применить действие игрока, если ожидалось
        if action is not None and self._waiting_uid is not None:
            actor = combat.get(self._waiting_uid)
            if actor is not None:
                if action.kind == ActionKind.FLEE:
                    # Групповой побег: все союзники кидают одновременно (§12)
                    for ally in list(combat.members(self.player_side)):
                        combat.attempt_flee(ally)
                    self._snapshot(phase="action", actor_uid=self._waiting_uid)
                    # Убрать оставшиеся ходы игрока в этом раунде
                    self._queue = [c for c in self._queue if c.side != self.player_side]
                elif actor.can_act:
                    self._apply(action, actor)
            self._waiting_uid = None

        # Крутить ходы до тех пор, пока не встретим ход игрока или конец боя
        while True:
            # Если бой закончился в середине раунда — очистить очередь
            if combat.is_over() and self._queue:
                self._queue.clear()

            if not self._queue:
                if self._round_active:
                    combat.end_round()
                    self._snapshot(phase="round_end", actor_uid=None)
                    self._round_active = False

                if combat.is_over() or combat.round >= self.max_rounds:
                    return self._build_result("over")

                # Начать новый раунд
                self._queue = list(combat.roll_initiative())
                self._round_active = True
                self._snapshot(phase="round_start", actor_uid=None)

            actor = self._queue.pop(0)

            if not actor.can_act:
                continue

            combat.trigger(actor, AbilityTrigger.ON_TURN_START)
            if not actor.can_act:
                continue

            if actor.side == self.player_side:
                self._waiting_uid = actor.uid
                return self._build_result("waiting", actor)

            # ИИ-ход
            ai_action = self._decide(actor)
            self._apply(ai_action, actor)

    # ── построение ответа ──

    def _build_result(self, status: str, actor: Optional[Combatant] = None) -> dict:
        new_events = self.events[self._last_sent:]
        self._last_sent = len(self.events)

        result: dict = {
            "status": status,
            "events": new_events,
            "combatants": [self._combatant_state(c) for c in self.combat.combatants],
        }

        if status == "waiting" and actor is not None:
            result["actor"] = self._actor_options(actor)

        if status == "over":
            outcome = self.outcome()
            side_label = {ALLY_SIDE: "Союзники", ENEMY_SIDE: "Враги"}
            result["outcome"] = {
                "winner": outcome.winner,
                "winner_label": side_label.get(outcome.winner) if outcome.winner else None,
                "rounds": outcome.rounds,
                "ended_by": outcome.ended_by,
                "survivors": outcome.survivors,
                "log": outcome.log,
            }

        return result

    def _actor_options(self, actor: Combatant) -> dict:
        combat = self.combat
        eligible = combat.eligible_single_targets(actor)
        eligible_uids = {c.uid for c in eligible}
        all_enemies = [c for c in combat.opponents_of(actor) if c.in_combat]

        return {
            "uid": actor.uid,
            "name": actor.name,
            "targets": [
                {
                    "uid": c.uid,
                    "name": c.name,
                    "available": c.uid in eligible_uids,
                    "has_bastion": c.has_bastion,
                    "hp": c.current_hp,
                    "max_hp": c.max_hp,
                }
                for c in all_enemies
            ],
            "ally_targets": [
                {"uid": c.uid, "name": c.name}
                for c in combat.members(actor.side)
                if c.uid != actor.uid and c.in_combat
            ],
            "spells": [
                {
                    "carrier_id": s.card_id,
                    "name": s.spell_name or s.name,
                    "damage": s.spell_damage_dice,
                    "difficulty": s.spell_difficulty,
                }
                for s in actor.spell_carriers
            ],
            "active_abilities": [
                {"name": ab.name, "source": ab.source_name}
                for ab in actor.abilities
                if ab.trigger == AbilityTrigger.ACTIVE.value
                and ab.once_per_combat
                and not ab.used
            ],
            "has_potion": any(it.is_potion for it in actor.inventory),
            "can_intimidate": self._check_intimidate(actor),
            "can_negotiate": self._check_negotiate(actor),
        }

    def _check_intimidate(self, actor: Combatant) -> dict:
        combat = self.combat
        if combat.special_mechanic_used:
            return {"available": False, "reason": "Спец. механика уже применялась в этом бою"}
        enemies = combat.opponents_of(actor)
        if not any(e.is_sentient and not e.is_dying for e in enemies):
            return {"available": False, "reason": "Нет разумных врагов"}
        my_str = sum(c.str_eff for c in combat.members(actor.side))
        enemy_str = sum(e.str_eff for e in enemies if not e.is_dying)
        if my_str <= enemy_str:
            return {"available": False, "reason": f"Сила союзников ({my_str}) ≤ силы врагов ({enemy_str})"}
        return {"available": True, "reason": None}

    def _check_negotiate(self, actor: Combatant) -> dict:
        combat = self.combat
        if combat.special_mechanic_used:
            return {"available": False, "reason": "Спец. механика уже применялась в этом бою"}
        enemies = combat.opponents_of(actor)
        if not any(e.is_sentient and not e.is_dying for e in enemies):
            return {"available": False, "reason": "Нет разумных врагов"}
        return {"available": True, "reason": None}


# ───────────────────────── сессии интерактивного боя ─────────────────────────


class BattleSession:
    def __init__(self, encounter: InteractiveEncounter) -> None:
        self.id: str = _uuid.uuid4().hex[:8]
        self.encounter = encounter


_SESSIONS: dict[str, BattleSession] = {}


def start_interactive(
    session: Session,
    ally_ids: list[int],
    enemy_ids: list[int],
    *,
    seed: Optional[int] = None,
) -> dict:
    """Создать интерактивный бой; вернуть начальное состояние."""
    if not ally_ids or not enemy_ids:
        raise ValueError("нужны участники с обеих сторон")

    rng = random.Random(seed)
    allies = _load_combatants(session, ally_ids, ALLY_SIDE)
    enemies = _load_combatants(session, enemy_ids, ENEMY_SIDE)

    combat = Combat(allies + enemies, rng=rng, session=session)
    encounter = InteractiveEncounter(
        combat,
        controllers={ALLY_SIDE: SimpleAIController(), ENEMY_SIDE: SimpleAIController()},
        player_side=ALLY_SIDE,
        max_rounds=50,
    )

    battle = BattleSession(encounter)
    _SESSIONS[battle.id] = battle

    result = encounter.begin()
    result["battle_id"] = battle.id
    result["roster"] = {
        ALLY_SIDE: [c.name for c in allies],
        ENEMY_SIDE: [c.name for c in enemies],
    }
    return result


def submit_action(battle_id: str, action_data: dict) -> dict:
    """Принять действие игрока, прокрутить ИИ-ходы, вернуть следующее состояние."""
    battle = _SESSIONS.get(battle_id)
    if battle is None:
        raise KeyError(battle_id)

    action = _parse_action(action_data)
    result = battle.encounter.submit(action)

    if result.get("status") == "over":
        _SESSIONS.pop(battle_id, None)

    return result


def _parse_action(data: dict) -> Action:
    kind_str = data.get("kind", "pass")
    kind_map = {k.value: k for k in ActionKind}
    kind = kind_map.get(kind_str, ActionKind.PASS)
    return Action(
        kind=kind,
        target_uid=data.get("target_uid"),
        carrier_card_id=data.get("carrier_card_id"),
        ability_name=data.get("ability_name"),
        enemy_side=data.get("enemy_side", ENEMY_SIDE),
    )


# ───────────────────────── автосимуляция ─────────────────────────


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
    """Прогнать автобой и вернуть события + итог."""
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
