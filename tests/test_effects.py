from grokhanika.enums import EffectTarget, EffectTargetType, SourceType
from grokhanika.rules.effects import (
    RuntimeEffect,
    add_effect,
    attr_modifier,
    roll_modifier,
    stat_modifier,
    tick_round,
)


def _morale():
    return RuntimeEffect(
        target_type=EffectTargetType.ATTR.value,
        target=EffectTarget.ALL_ATTACK_ROLLS.value,
        modifier=-2,
        duration=0,
        source_type=SourceType.MORALE.value,
        is_stackable=False,
    )


def test_non_stackable_refreshes_duration():
    active: list[RuntimeEffect] = []
    e1 = RuntimeEffect("stat", "strength", 1, duration=2, source_id=7, is_stackable=False)
    e2 = RuntimeEffect("stat", "strength", 1, duration=5, source_id=7, is_stackable=False)
    add_effect(active, e1)
    add_effect(active, e2)
    assert len(active) == 1
    assert active[0].duration == 5  # длительность обновилась, не сложилась


def test_stackable_accumulates():
    active: list[RuntimeEffect] = []
    add_effect(active, RuntimeEffect("stat", "strength", 1, source_id=1))
    add_effect(active, RuntimeEffect("stat", "strength", 1, source_id=2))
    assert stat_modifier(active, "strength") == 2


def test_tick_round_decrements_and_removes():
    active = [RuntimeEffect("stat", "strength", 1, duration=2)]
    assert tick_round(active) == []  # 2 -> 1, не снят
    removed = tick_round(active)     # 1 -> 0, снят
    assert len(removed) == 1 and active == []


def test_permanent_effects_never_tick():
    active = [RuntimeEffect("attr", "hp", 5, duration=0)]
    tick_round(active)
    assert active and active[0].duration == 0


def test_roll_modifier_distinguishes_attack_and_save():
    talisman = RuntimeEffect("attr", EffectTarget.ALL_D20_ROLLS.value, 2)
    morale = _morale()
    effects = [talisman, morale]
    # атака: и талисман, и мораль
    assert roll_modifier(effects, attack=True) == 0  # +2 - 2
    # спасбросок/защита: только талисман
    assert roll_modifier(effects, attack=False) == 2


def test_morale_not_stackable_in_practice():
    active: list[RuntimeEffect] = []
    add_effect(active, _morale())
    add_effect(active, _morale())  # повторный провал не суммируется
    assert len([e for e in active if e.source_type == "morale"]) == 1
    assert attr_modifier(active, EffectTarget.ALL_ATTACK_ROLLS) == -2
