"""Ментальные групповые способности: бафф сопартийцев / дебафф врагов (§10)."""
import random

from grokhanika.engine import (
    Combat,
    Combatant,
    Encounter,
    SimpleAIController,
)
from grokhanika.engine.actions import ActionKind
from grokhanika.rules.effects import roll_modifier

from .conftest import ScriptedRandom


def test_buff_allies_hits_whole_party_not_enemies(catalog):
    enzo = Combatant(catalog["enzo"], "party")  # несёт «Лютню вдохновения»
    andr = Combatant(catalog["andryusha"], "party")
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([enzo, andr, goblin], rng=ScriptedRandom())

    fired = combat.activate_ability(enzo, "Песнь храбрости")
    assert "Песнь храбрости" in fired
    # бафф навешен и на кастующего (поверх его талисмана удачи), и на сопартийца
    assert any("Воодушевление" in e.description for e in enzo.active_effects)
    assert roll_modifier(andr.active_effects, attack=True) == 2
    assert roll_modifier(andr.active_effects, attack=False) == 2
    # враг не затронут
    assert roll_modifier(goblin.active_effects, attack=True) == 0


def test_debuff_enemies_is_contested_per_target(catalog):
    necro = Combatant(catalog["necromancer"], "enemy")  # «Леденящий взор»
    andr = Combatant(catalog["andryusha"], "party")  # мент.защ 7
    salli = Combatant(catalog["salli"], "party")     # мент.защ 6
    # порядок врагов = [andr, salli]; на каждого по 2 d20 (атака, защита)
    # andr: atk 20+3=23 vs def 1+7=8 -> успех;  salli: atk 1+3=4 vs def 1+6=7 -> провал
    combat = Combat([andr, salli, necro], rng=ScriptedRandom(ints=[20, 1, 1, 1]))

    combat.activate_ability(necro, "Леденящий взор")
    # дебафф только на броски атаки (не на спасброски/защиту)
    assert roll_modifier(andr.active_effects, attack=True) == -2
    assert roll_modifier(andr.active_effects, attack=False) == 0
    # салли спаслась
    assert roll_modifier(salli.active_effects, attack=True) == 0


def test_active_ability_is_once_per_combat(catalog):
    enzo = Combatant(catalog["enzo"], "party")
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([enzo, goblin], rng=ScriptedRandom())

    assert combat.activate_ability(enzo, "Песнь храбрости")
    assert not combat.activate_ability(enzo, "Песнь храбрости")  # повторно нельзя


def test_ai_activates_group_ability_first(catalog):
    enzo = Combatant(catalog["enzo"], "party")
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([enzo, goblin], rng=ScriptedRandom())

    action = SimpleAIController().decide(combat, enzo)
    assert action.kind is ActionKind.ACTIVATE_ABILITY
    assert action.ability_name == "Песнь храбрости"


def test_buff_appears_in_encounter(catalog, session):
    rng = random.Random(11)
    party = [Combatant(catalog[k], "party") for k in ("enzo", "andryusha")]
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat(party + [goblin], rng=rng, session=session)

    enc = Encounter(
        combat,
        {"party": SimpleAIController(), "enemy": SimpleAIController()},
        max_rounds=20,
    )
    outcome = enc.run()
    assert any("воодушевляет союзников" in line for line in outcome.log)
    assert outcome.winner == "party"
