"""Движок уникальных способностей: data-driven «триггер → действия».

Карточка несёт способности как данные (``Ability.actions`` — список словарей).
Вокабуляр действий фиксирован кодом-обработчиками в ``ACTION_HANDLERS`` и легко
расширяется новым обработчиком, без изменения схемы БД. Это покрывает запрос:
«призывать существ», «мгновенно убивать по вероятности» и т.п.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..dice import Dice
from ..enums import ActionType, SourceType
from ..rules.effects import RuntimeEffect
from .combatant import AbilitySpec, Combatant


@dataclass
class AbilityContext:
    actor: Combatant
    rng: random.Random
    combat: object = None  # engine.combat.Combat (избегаем циклического импорта)
    target: Optional[Combatant] = None
    log: list[str] = field(default_factory=list)


ActionHandler = Callable[[dict, AbilityContext], None]
ACTION_HANDLERS: dict[str, ActionHandler] = {}


def action_handler(action_type: ActionType) -> Callable[[ActionHandler], ActionHandler]:
    def deco(fn: ActionHandler) -> ActionHandler:
        ACTION_HANDLERS[action_type.value] = fn
        return fn

    return deco


# ───────────────────────── обработчики действий ─────────────────────────


@action_handler(ActionType.DAMAGE)
def _damage(action: dict, ctx: AbilityContext) -> None:
    target = ctx.target
    if target is None:
        return
    dice = Dice.parse(action["dice"])
    amount = dice.roll(ctx.rng) + int(action.get("bonus", 0))
    dealt = target.take_damage(amount)
    ctx.log.append(f"{ctx.actor.name}: способность наносит {dealt} урона {target.name}")


@action_handler(ActionType.HEAL)
def _heal(action: dict, ctx: AbilityContext) -> None:
    target = ctx.target or ctx.actor
    dice = Dice.parse(action["dice"])
    healed = target.heal(dice.roll(ctx.rng) + int(action.get("bonus", 0)))
    ctx.log.append(f"{ctx.actor.name}: способность лечит {target.name} на {healed}")


@action_handler(ActionType.INSTAKILL)
def _instakill(action: dict, ctx: AbilityContext) -> None:
    target = ctx.target
    if target is None:
        return
    chance = float(action.get("chance", 1.0))
    if ctx.rng.random() <= chance:
        target.current_hp = 0
        target.dead = True
        ctx.log.append(f"{ctx.actor.name}: МГНОВЕННОЕ УБИЙСТВО — {target.name} погибает")
    else:
        ctx.log.append(f"{ctx.actor.name}: мгновенное убийство не сработало на {target.name}")


@action_handler(ActionType.APPLY_EFFECT)
def _apply_effect(action: dict, ctx: AbilityContext) -> None:
    target = ctx.target or ctx.actor
    eff = action["effect"]
    target.add_temporary_effect(
        RuntimeEffect(
            target_type=eff["target_type"],
            target=eff["target"],
            modifier=int(eff.get("modifier", 0)),
            duration=int(eff.get("duration", 0)),
            source_type=eff.get("source_type", SourceType.SPELL.value),
            source_id=ctx.actor.card_id,
            is_stackable=bool(eff.get("is_stackable", True)),
            description=eff.get("description", ""),
        )
    )
    ctx.log.append(f"{ctx.actor.name}: способность вешает эффект на {target.name}")


@action_handler(ActionType.SUMMON)
def _summon(action: dict, ctx: AbilityContext) -> None:
    combat = ctx.combat
    if combat is None or getattr(combat, "session", None) is None:
        ctx.log.append(f"{ctx.actor.name}: призыв невозможен (нет доступа к БД)")
        return
    from ..db.models import Creature  # локальный импорт во избежание цикла

    creature = combat.session.get(Creature, action["creature_id"])
    if creature is None:
        return
    count = int(action.get("count", 1))
    for _ in range(count):
        summoned = Combatant(creature, ctx.actor.side)
        combat.add_combatant(summoned)
        ctx.log.append(f"{ctx.actor.name}: призывает {summoned.name}")


@action_handler(ActionType.APPLY_MORALE)
def _apply_morale(action: dict, ctx: AbilityContext) -> None:
    combat = ctx.combat
    if combat is None:
        return
    side = action.get("side", ctx.actor.side)
    combat.apply_morale_debuff(side)
    ctx.log.append(f"{ctx.actor.name}: дебафф морали на сторону {side}")


# ───────────────────────── запуск способностей ─────────────────────────


def _condition_ok(spec: AbilitySpec, ctx: AbilityContext) -> bool:
    cond = spec.condition or {}
    target = ctx.target
    if cond.get("target_is_sentient") and not (target and target.is_sentient):
        return False
    if cond.get("target_is_dying") and not (target and target.is_dying):
        return False
    return True


def fire_abilities(
    owner: Combatant,
    trigger,
    ctx: AbilityContext,
    *,
    target: Optional[Combatant] = None,
) -> list[str]:
    """Запустить все способности владельца с данным триггером.

    Возвращает имена сработавших способностей. Учитывает ``once_per_combat``,
    вероятность ``chance`` и условия ``condition``.
    """
    trigger_value = trigger.value if hasattr(trigger, "value") else trigger
    if target is not None:
        ctx.target = target

    fired: list[str] = []
    for spec in owner.abilities:
        if spec.trigger != trigger_value:
            continue
        if spec.once_per_combat and spec.used:
            continue
        if not _condition_ok(spec, ctx):
            continue
        if spec.chance is not None and ctx.rng.random() > spec.chance:
            continue

        if spec.once_per_combat:
            spec.used = True
        for act in spec.actions:
            handler = ACTION_HANDLERS.get(act.get("type"))
            if handler is None:
                ctx.log.append(f"{owner.name}: неизвестное действие {act.get('type')!r}")
                continue
            handler(act, ctx)
        fired.append(spec.name)
    return fired
