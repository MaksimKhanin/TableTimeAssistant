"""Тесты data-driven способностей (триггер → действие)."""
from grokhanika.db.models import Creature
from grokhanika.engine.abilities import AbilityContext, fire_abilities
from grokhanika.engine.combat import Combat
from grokhanika.engine.combatant import Combatant
from grokhanika.enums import AbilityTrigger

from .conftest import ScriptedRandom


def test_summon_on_combat_start(catalog, session):
    necromancer = Combatant(catalog["necromancer"], "enemy")
    hero = Combatant(catalog["andryusha"], "party")
    combat = Combat([hero, necromancer], rng=ScriptedRandom(), session=session)

    combat.fire_combat_start()

    enemies = combat.members("enemy")
    assert len(enemies) == 3  # некромант + 2 призванных гоблина
    assert sum(1 for c in enemies if c.name == "Гоблин") == 2


def test_summon_is_once_per_combat(catalog, session):
    necromancer = Combatant(catalog["necromancer"], "enemy")
    combat = Combat([necromancer], rng=ScriptedRandom(), session=session)
    combat.fire_combat_start()
    combat.fire_combat_start()  # второй раз не должен призывать снова
    assert sum(1 for c in combat.members("enemy") if c.name == "Гоблин") == 2


def test_instakill_on_hit_triggers(catalog):
    # d20=15 -> попадание; floats: 0.1 (проходит шанс 0.25), 0.5 (instakill chance 1.0)
    rng = ScriptedRandom(ints=[15], floats=[0.1, 0.5])
    assassin = Combatant(catalog["assassin"], "enemy")
    enzo = Combatant(catalog["enzo"], "party")
    combat = Combat([assassin, enzo], rng=rng)

    res = combat.physical_attack(assassin, enzo)
    assert res.hit and res.killed
    assert enzo.dead and enzo.current_hp == 0


def test_instakill_respects_chance(catalog):
    # floats: 0.9 > шанс 0.25 -> способность не срабатывает
    rng = ScriptedRandom(ints=[15], floats=[0.9])
    assassin = Combatant(catalog["assassin"], "enemy")
    enzo = Combatant(catalog["enzo"], "party")
    combat = Combat([assassin, enzo], rng=rng)

    combat.physical_attack(assassin, enzo)
    assert not enzo.dead  # получил обычный урон, но жив


def test_condition_blocks_ability_on_non_sentient_target(catalog):
    dummy = Creature(
        name="Манекен", is_sentient=False, hp=50, dexterity=1,
        phys_defense=1, mag_defense=0, mental_defense=1, phys_damage_dice="1d4",
        strength=1, charisma=1, wisdom=1,
    )
    assassin = Combatant(catalog["assassin"], "enemy")
    target = Combatant(dummy, "party")
    rng = ScriptedRandom(ints=[20], floats=[0.0, 0.0])
    combat = Combat([assassin, target], rng=rng)

    combat.physical_attack(assassin, target)
    # цель не разумна -> condition target_is_sentient не выполнено -> instakill не сработал
    assert not target.dead


def test_unknown_action_is_logged_not_crashing(catalog):
    from grokhanika.engine.combatant import AbilitySpec

    enzo = Combatant(catalog["enzo"], "party")
    enzo.abilities.append(
        AbilitySpec(name="Глюк", trigger=AbilityTrigger.ON_HIT.value, actions=[{"type": "nonsense"}])
    )
    ctx = AbilityContext(actor=enzo, rng=ScriptedRandom())
    fired = fire_abilities(enzo, AbilityTrigger.ON_HIT, ctx)
    assert "Глюк" in fired
    assert any("неизвестное действие" in line for line in ctx.log)
