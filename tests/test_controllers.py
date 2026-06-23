from grokhanika.engine import Combat, Combatant, ScriptedController, SimpleAIController
from grokhanika.engine.actions import Action, ActionKind

from .conftest import ScriptedRandom


def test_scripted_controller_yields_then_passes():
    ctrl = ScriptedController([Action.attack(1), Action.flee()])
    assert ctrl.decide(None, None).kind is ActionKind.ATTACK_PHYSICAL
    assert ctrl.decide(None, None).kind is ActionKind.FLEE
    assert ctrl.decide(None, None).kind is ActionKind.PASS  # очередь исчерпана


def test_ai_targets_lowest_hp_enemy(catalog):
    andr = Combatant(catalog["andryusha"], "party")
    g1 = Combatant(catalog["goblin"], "enemy")
    g2 = Combatant(catalog["goblin"], "enemy")
    g2.current_hp = 2  # самый раненый — добиваем его
    combat = Combat([andr, g1, g2], rng=ScriptedRandom())

    action = SimpleAIController().decide(combat, andr)
    assert action.kind is ActionKind.ATTACK_PHYSICAL
    assert action.target_uid == g2.uid


def test_ai_casts_when_caster_and_has_carrier(catalog):
    arseldor = Combatant(catalog["arseldor"], "party")  # маг.атака 9 >= физ 1, есть том
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([arseldor, goblin], rng=ScriptedRandom())

    action = SimpleAIController().decide(combat, arseldor)
    assert action.kind is ActionKind.CAST_SPELL
    assert action.carrier_card_id == catalog["tome_arrows"].id


def test_ai_drinks_potion_when_low(catalog):
    enzo = Combatant(catalog["enzo"], "party")  # в инвентаре малое зелье
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([enzo, goblin], rng=ScriptedRandom())
    enzo.current_hp = 2  # ниже порога 35%

    action = SimpleAIController().decide(combat, enzo)
    assert action.kind is ActionKind.USE_POTION


def test_ai_passes_without_targets(catalog):
    andr = Combatant(catalog["andryusha"], "party")
    combat = Combat([andr], rng=ScriptedRandom())
    assert SimpleAIController().decide(combat, andr).kind is ActionKind.PASS
