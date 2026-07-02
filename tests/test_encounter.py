import random

from grokhanika.db.models import Scroll
from grokhanika.engine import (
    Combat,
    Combatant,
    Encounter,
    ScriptedController,
    SimpleAIController,
)
from grokhanika.engine.actions import Action

from .conftest import ScriptedRandom


def test_ai_battle_terminates_with_winner(catalog, session):
    rng = random.Random(7)
    party = [Combatant(catalog[k], "party") for k in ("andryusha", "salli")]
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat(party + [goblin], rng=rng, session=session)

    enc = Encounter(
        combat,
        {"party": SimpleAIController(), "enemy": SimpleAIController()},
        max_rounds=30,
    )
    outcome = enc.run()

    assert combat.is_over()
    assert outcome.winner == "party"
    assert outcome.ended_by == "rout"
    assert outcome.rounds <= 30


def test_negotiation_ends_encounter(catalog):
    # инициатива (2 d20), затем переговоры Андрюши: atk d20=20, def d20=1 -> успех
    rng = ScriptedRandom(ints=[1, 1, 20, 1])
    andr = Combatant(catalog["andryusha"], "party")
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([andr, goblin], rng=rng)

    enc = Encounter(
        combat,
        {"party": ScriptedController([Action.negotiate("enemy")]), "enemy": ScriptedController([])},
        max_rounds=5,
    )
    outcome = enc.run()
    assert outcome.ended_by == "negotiation"
    assert combat.finished_by_negotiation


def test_flee_removes_combatant(catalog):
    # инициатива (2 d20), затем побег Андрюши: d20=8 -> 8 + DEX_eff(2) = 10 >= 10 выжил
    rng = ScriptedRandom(ints=[1, 1, 8])
    andr = Combatant(catalog["andryusha"], "party")
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([andr, goblin], rng=rng)

    enc = Encounter(
        combat,
        {"party": ScriptedController([Action.flee()]), "enemy": ScriptedController([])},
        max_rounds=5,
    )
    outcome = enc.run()
    assert andr.escaped
    assert outcome.winner == "enemy"  # партия покинула бой


def test_timeout_when_nobody_acts(catalog):
    rng = ScriptedRandom()
    andr = Combatant(catalog["andryusha"], "party")
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([andr, goblin], rng=rng)

    enc = Encounter(
        combat,
        {"party": ScriptedController([]), "enemy": ScriptedController([])},  # все пасуют
        max_rounds=3,
    )
    outcome = enc.run()
    assert outcome.ended_by == "timeout"
    assert outcome.rounds == 3
    assert outcome.winner is None


def test_scroll_consumed_after_cast(catalog, session):
    scroll = Scroll(
        name="Свиток искры", spell_name="Искра",
        damage_dice="1d6", difficulty=5, attack_stat="wisdom", price=5,
    )
    catalog["arseldor"].inventory.append(scroll)
    session.add(scroll)
    session.flush()

    arseldor = Combatant(catalog["arseldor"], "party")
    goblin = Combatant(catalog["goblin"], "enemy")
    # активация d20=5 -> 5+маг.атака(9)=14 >= сл.5; спас d20=1 -> провал
    combat = Combat([arseldor, goblin], rng=ScriptedRandom(ints=[5, 1]))

    assert any(it.card_id == scroll.id for it in arseldor.inventory)
    res = combat.cast_from_carrier(arseldor, goblin, scroll.id)
    assert res is not None and res.activated
    # свиток израсходован и исчез из инвентаря
    assert not any(it.card_id == scroll.id for it in arseldor.inventory)
