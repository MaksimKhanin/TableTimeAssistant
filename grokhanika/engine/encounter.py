"""Менеджер боя — оркестрация поверх ``Combat``.

``Combat`` остаётся сводом правил; ``Encounter`` гоняет цикл: старт, раунды,
ходы участников (через контроллеры), конец раунда, итог. Инициатива
пересчитывается в начале каждого раунда (учёт призванных и дебаффов на DEX).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from ..enums import AbilityTrigger
from .actions import Action, ActionKind
from .combat import Combat
from .combatant import Combatant
from .controllers import Controller


@dataclass
class Outcome:
    winner: Optional[str]
    rounds: int
    ended_by: str  # 'rout' | 'negotiation' | 'timeout' | 'draw'
    survivors: dict[str, list[str]] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)


class Encounter:
    def __init__(
        self,
        combat: Combat,
        controllers: Mapping[str, Controller],
        *,
        max_rounds: int = 50,
    ) -> None:
        self.combat = combat
        self.controllers = dict(controllers)
        self.max_rounds = max_rounds
        self._started = False

    # ───────── жизненный цикл ─────────

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.combat.fire_combat_start()

    def run_round(self) -> None:
        """Один раунд: инициатива → ходы → конец раунда."""
        combat = self.combat
        for actor in combat.roll_initiative():
            if combat.is_over():
                break
            if not actor.can_act:  # Dying / сбежал / погиб
                continue
            combat.trigger(actor, AbilityTrigger.ON_TURN_START)
            if not actor.can_act:  # способность могла его вывести из строя
                continue
            self._apply(self._decide(actor), actor)
        combat.end_round()

    def run(self) -> Outcome:
        """Прогнать бой целиком и вернуть итог."""
        self.start()
        while not self.combat.is_over() and self.combat.round < self.max_rounds:
            self.run_round()
        return self.outcome()

    # ───────── решения и применение ─────────

    def _decide(self, actor: Combatant) -> Action:
        controller = self.controllers.get(actor.side)
        if controller is None:
            return Action.do_nothing()
        return controller.decide(self.combat, actor)

    def _default_enemy_side(self, actor: Combatant) -> Optional[str]:
        opponents = self.combat.opponents_of(actor)
        return opponents[0].side if opponents else None

    def _apply(self, action: Action, actor: Combatant) -> None:
        combat = self.combat
        kind = action.kind

        if kind is ActionKind.PASS:
            combat.log.append(f"{actor.name} пропускает ход")
            return

        if kind is ActionKind.USE_POTION:
            combat.use_potion(actor, action.item_name)
            return

        if kind is ActionKind.FLEE:
            combat.attempt_flee(actor)
            return

        if kind is ActionKind.ACTIVATE_ABILITY:
            target = combat.get(action.target_uid) if action.target_uid is not None else None
            if not combat.activate_ability(actor, action.ability_name, target):
                combat.log.append(
                    f"{actor.name}: способность «{action.ability_name}» недоступна — ход впустую"
                )
            return

        if kind in (ActionKind.INTIMIDATE, ActionKind.NEGOTIATE):
            enemy_side = action.enemy_side or self._default_enemy_side(actor)
            if enemy_side is None:
                combat.log.append(f"{actor.name}: нет вражеской стороны для спец. механики")
                return
            if kind is ActionKind.INTIMIDATE:
                combat.intimidate(actor, enemy_side)
            else:
                combat.negotiate(actor, enemy_side)
            return

        # атакующие действия требуют валидную цель
        target = combat.get(action.target_uid) if action.target_uid is not None else None
        if target is None or not target.in_combat:
            combat.log.append(f"{actor.name}: цель недоступна — ход потрачен впустую")
            return

        # «Бастион»: одиночную атаку нельзя нацелить мимо живых носителей Бастиона
        if combat.bastion_blocks(actor, target):
            combat.log.append(
                f"{actor.name}: {target.name} под защитой Бастиона — "
                f"сначала нужно убить носителей Бастиона"
            )
            return

        if kind is ActionKind.ATTACK_PHYSICAL:
            combat.physical_attack(actor, target)
        elif kind is ActionKind.CAST_SPELL:
            combat.cast_from_carrier(actor, target, action.carrier_card_id)
        elif kind is ActionKind.ATTACK_MENTAL:
            combat.mental_attack(actor, target, effect=action.effect)

    # ───────── итог ─────────

    def outcome(self) -> Outcome:
        combat = self.combat
        winner = combat.winner()
        if combat.finished_by_negotiation:
            ended_by = "negotiation"
        elif winner is not None:
            ended_by = "rout"
        elif combat.round >= self.max_rounds:
            ended_by = "timeout"
        else:
            ended_by = "draw"

        # «выжившие» — стоящие на ногах (в бою и не Dying)
        survivors = {
            side: [c.name for c in combat.members(side) if not c.is_dying]
            for side in sorted(combat.sides())
        }
        return Outcome(
            winner=winner,
            rounds=combat.round,
            ended_by=ended_by,
            survivors=survivors,
            log=list(combat.log),
        )
