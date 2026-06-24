"""Тесты механики «Бастион» (taunt): одиночные атаки обязаны бить носителей строя."""
from grokhanika.engine import Combat, Combatant, Encounter, ScriptedController
from grokhanika.engine.actions import Action
from grokhanika.engine.combatant import AbilitySpec
from grokhanika.engine.controllers import SimpleAIController
from grokhanika.enums import (
    AbilityTrigger,
    ActionType,
    EffectTarget,
    EffectTargetType,
    SourceType,
)

from .conftest import ScriptedRandom


def test_bastion_marker_from_item(catalog):
    # Андрюша носит «Защитник Импродора» → пассивный навык «Бастион»
    andr = Combatant(catalog["andryusha"], "party")
    assert andr.has_bastion
    assert not Combatant(catalog["enzo"], "party").has_bastion


def test_bastion_keeps_andryusha_stats(catalog):
    # Уникальный щит даёт те же характеристики, что деревянный (физ.защ 9)
    andr = Combatant(catalog["andryusha"], "party")
    assert andr.phys_defense == 9 and andr.dex_eff == 2


def test_single_attack_on_non_guard_blocked(catalog):
    andr = Combatant(catalog["andryusha"], "party")   # бастион
    enzo = Combatant(catalog["enzo"], "party")         # обычный
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([andr, enzo, goblin], rng=ScriptedRandom())

    assert combat.bastion_blocks(goblin, enzo) is True    # прикрыт строем
    assert combat.bastion_blocks(goblin, andr) is False   # сам бастион — можно бить


def test_ai_targets_bastion_holder_first(catalog):
    andr = Combatant(catalog["andryusha"], "party")
    enzo = Combatant(catalog["enzo"], "party")
    enzo.current_hp = 1  # даже у самого слабого нельзя — строй держит бастион
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([andr, enzo, goblin], rng=ScriptedRandom())

    assert SimpleAIController()._pick_target(combat, goblin) is andr
    assert combat.eligible_single_targets(goblin) == [andr]


def test_dying_bastion_frees_others(catalog):
    andr = Combatant(catalog["andryusha"], "party")
    enzo = Combatant(catalog["enzo"], "party")
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([andr, enzo, goblin], rng=ScriptedRandom())

    andr.current_hp = 0  # бастион в Dying — больше не держит строй
    assert not combat.bastion_blocks(goblin, enzo)
    assert SimpleAIController()._pick_target(combat, goblin) is enzo


def test_must_kill_all_bastions(catalog):
    # два носителя Бастиона — врага нужно пробить через обоих
    g1 = Combatant(catalog["andryusha"], "party")
    g2 = Combatant(catalog["andryusha"], "party")
    enzo = Combatant(catalog["enzo"], "party")
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([g1, g2, enzo, goblin], rng=ScriptedRandom())

    assert combat.bastion_blocks(goblin, enzo)
    g1.current_hp = 0
    assert combat.bastion_blocks(goblin, enzo)       # второй бастион ещё жив
    g2.current_hp = 0
    assert not combat.bastion_blocks(goblin, enzo)   # пали оба — строй сломлен


def test_mass_ability_ignores_bastion(catalog):
    # массовая способность задевает и не-бастиона, несмотря на активный Бастион
    andr = Combatant(catalog["andryusha"], "party")
    enzo = Combatant(catalog["enzo"], "party")
    goblin = Combatant(catalog["goblin"], "enemy")
    goblin.abilities.append(
        AbilitySpec(
            name="Боевой клич", trigger=AbilityTrigger.ACTIVE.value, once_per_combat=True,
            actions=[{
                "type": ActionType.DEBUFF_ENEMIES.value,
                "effect": {
                    "target_type": EffectTargetType.ATTR.value,
                    "target": EffectTarget.ALL_ATTACK_ROLLS.value,
                    "modifier": -2, "duration": 3,
                    "source_type": SourceType.ITEM.value, "description": "клич",
                },
            }],
        )
    )
    # контест против каждого врага: высокий бросок атаки, низкий — защиты
    combat = Combat([andr, enzo, goblin], rng=ScriptedRandom(ints=[20, 1, 20, 1]))
    combat.activate_ability(goblin, "Боевой клич")

    debuffed = lambda c: any(e.target == EffectTarget.ALL_ATTACK_ROLLS.value for e in c.temporary_effects)
    assert debuffed(enzo)   # массовый дебафф достал не-бастиона
    assert debuffed(andr)


def test_encounter_blocks_attack_targeting_non_guard(catalog, session):
    # скриптовый контроллер пытается ударить не-бастиона мимо строя → ход впустую
    andr = Combatant(catalog["andryusha"], "party")   # бастион
    enzo = Combatant(catalog["enzo"], "party")
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([andr, enzo, goblin], rng=ScriptedRandom(ints=[20, 20]), session=session)
    enzo_hp = enzo.current_hp

    enc = Encounter(
        combat,
        {"enemy": ScriptedController([Action.attack(enzo.uid)]), "party": ScriptedController([])},
        max_rounds=1,
    )
    enc.start()
    enc.run_round()

    assert enzo.current_hp == enzo_hp  # удар не прошёл — Бастион прикрыл
    assert any("под защитой Бастиона" in line for line in combat.log)
