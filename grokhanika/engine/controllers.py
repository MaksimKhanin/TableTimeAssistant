"""Контроллеры — кто принимает решение за участника на его ход.

Движок боя (``Encounter``) не зашивает ИИ: у каждой стороны есть контроллер,
который по состоянию боя возвращает ``Action``. Так один движок крутит автобой
(``SimpleAIController``), тесты/реплеи (``ScriptedController``) и — в будущем —
живых игроков.
"""
from __future__ import annotations

from typing import Iterable, Iterator, Optional, Protocol, runtime_checkable

from ..enums import AbilityTrigger
from .actions import Action
from .combatant import Combatant


@runtime_checkable
class Controller(Protocol):
    def decide(self, combat, actor: Combatant) -> Action:
        ...


class ScriptedController:
    """Отдаёт заранее заданные действия по очереди; по исчерпании — PASS."""

    def __init__(self, actions: Iterable[Action]) -> None:
        self._actions: Iterator[Action] = iter(actions)

    def decide(self, combat, actor: Combatant) -> Action:
        return next(self._actions, Action.do_nothing())


class SimpleAIController:
    """Простой ИИ для NPC/монстров.

    Приоритеты:
      1. при низком HP и наличии зелья — выпить зелье;
      2. если есть атакующий том/свиток и маг.атака не слабее физ. — каст;
      3. иначе — физическая атака по первому живому врагу;
      4. нет целей — PASS.
    """

    def __init__(self, *, heal_below: float = 0.35) -> None:
        self.heal_below = heal_below

    def decide(self, combat, actor: Combatant) -> Action:
        if (
            actor.current_hp <= actor.max_hp * self.heal_below
            and any(it.is_potion for it in actor.inventory)
        ):
            return Action.potion()

        target = self._pick_target(combat, actor)
        if target is None:
            return Action.do_nothing()

        # одноразовая активная способность (бафф/дебафф) — применяем сразу
        active = self._available_active(actor)
        if active is not None:
            return Action.activate(active.name)

        carrier = self._best_spell_carrier(actor)
        if carrier is not None and actor.mag_attack_bonus >= actor.phys_attack_bonus:
            return Action.cast(target.uid, carrier.card_id)
        return Action.attack(target.uid)

    @staticmethod
    def _available_active(actor: Combatant):
        for spec in actor.abilities:
            if (
                spec.trigger == AbilityTrigger.ACTIVE.value
                and spec.once_per_combat
                and not spec.used
            ):
                return spec
        return None

    @staticmethod
    def _pick_target(combat, actor: Combatant) -> Optional[Combatant]:
        living = [t for t in combat.opponents_of(actor) if not t.is_dying]
        if not living:
            return None
        # цель с наименьшим текущим HP — добиваем
        return min(living, key=lambda t: t.current_hp)

    @staticmethod
    def _best_spell_carrier(actor: Combatant):
        # источники заклинаний: тома/свитки в инвентаре + навыки-заклинания
        carriers = actor.spell_carriers
        return carriers[0] if carriers else None
