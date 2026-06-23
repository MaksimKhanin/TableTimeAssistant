from grokhanika.enums import HPState
from grokhanika.engine.combat import Combat
from grokhanika.engine.combatant import Combatant

from .conftest import ScriptedRandom


def make_combat(catalog, party_keys, enemy_keys, rng):
    party = [Combatant(catalog[k], "party") for k in party_keys]
    enemies = [Combatant(catalog[k], "enemy") for k in enemy_keys]
    return Combat(party + enemies, rng=rng), party, enemies


# ───────── физическая атака (§8) ─────────

def test_physical_hit_deals_damage(catalog):
    rng = ScriptedRandom(ints=[15])  # d20=15; кубики урона падают на минимум
    combat, (andryusha,), (goblin,) = make_combat(catalog, ["andryusha"], ["goblin"], rng)
    res = combat.physical_attack(andryusha, goblin)
    # total = 15 + phys_atk(1) = 16 >= goblin.phys_defense(8)
    assert res.hit and not res.crit
    assert res.damage == 1 + 6  # 1d8 минимум + STR//2(6)
    assert goblin.current_hp == 8 - 7


def test_physical_crit_doubles_dice(catalog):
    rng = ScriptedRandom(ints=[20])
    combat, (andryusha,), (goblin,) = make_combat(catalog, ["andryusha"], ["goblin"], rng)
    res = combat.physical_attack(andryusha, goblin)
    assert res.crit and res.hit
    assert res.damage == 2 * 1 + 6  # 2 кубика d8 по минимуму + бонус
    assert goblin.current_hp == 0 and res.killed


def test_natural_one_is_auto_miss(catalog):
    rng = ScriptedRandom(ints=[1])
    combat, (andryusha,), (goblin,) = make_combat(catalog, ["andryusha"], ["goblin"], rng)
    res = combat.physical_attack(andryusha, goblin)
    assert res.fumble and not res.hit and res.damage == 0


def test_luck_talisman_applies_to_attack_roll(catalog):
    rng = ScriptedRandom(ints=[5])
    combat, (enzo,), (goblin,) = make_combat(catalog, ["enzo"], ["goblin"], rng)
    res = combat.physical_attack(enzo, goblin)
    # total = 5 + phys_atk(6) + талисман(+2) = 13
    assert res.total == 13


# ───────── магическая атака (§9) ─────────

def test_magic_save_halves_damage(catalog):
    # активация d20=5 -> 5 + mag_atk(9) = 14 >= сл.10; спас d20=20 -> высокий -> спас успешен
    rng = ScriptedRandom(ints=[5, 20])
    combat, (arseldor,), (goblin,) = make_combat(catalog, ["arseldor"], ["goblin"], rng)
    res = combat.magical_attack(arseldor, goblin, damage_dice="4d4", difficulty=10)
    assert res.activated and res.saved
    assert res.damage == 2  # 4d4 минимум = 4, ceil(4/2) = 2


def test_magic_full_damage_on_failed_save(catalog):
    rng = ScriptedRandom(ints=[5, 1])
    combat, (arseldor,), (goblin,) = make_combat(catalog, ["arseldor"], ["goblin"], rng)
    res = combat.magical_attack(arseldor, goblin, damage_dice="4d4", difficulty=10)
    assert res.activated and res.saved is False
    assert res.damage == 4


def test_magic_activation_can_fail(catalog):
    rng = ScriptedRandom(ints=[1])  # натуральная 1 -> провал активации
    combat, (arseldor,), (goblin,) = make_combat(catalog, ["arseldor"], ["goblin"], rng)
    res = combat.magical_attack(arseldor, goblin, damage_dice="1d10", difficulty=8)
    assert not res.activated and res.damage == 0


# ───────── инициатива (§7) ─────────

def test_initiative_orders_by_dex(catalog):
    rng = ScriptedRandom(ints=[10, 10, 10, 10])
    combat, party, enemies = make_combat(
        catalog, ["enzo", "arseldor"], ["goblin"], rng
    )
    order = combat.roll_initiative()
    # Энцо DEX_eff 12 > Гоблин 4 > Арсельдор 3
    assert [c.name for c in order][0] == "Энцо"
    assert order[-1].name == "Арсельдор"


# ───────── состояния HP и зелья (§11) ─────────

def test_potion_revives_dying_character(catalog):
    rng = ScriptedRandom(ints=[3])  # 1d4 -> 3
    enzo = Combatant(catalog["enzo"], "party")
    combat = Combat([enzo], rng=rng)
    enzo.current_hp = 0
    assert enzo.state is HPState.DYING
    healed = combat.use_potion(enzo, "Малое зелье лечения")
    assert healed == 3 and enzo.state is HPState.ACTIVE


def test_overheal_capped_at_max(catalog):
    rng = ScriptedRandom(ints=[4])
    enzo = Combatant(catalog["enzo"], "party")
    combat = Combat([enzo], rng=rng)
    enzo.current_hp = enzo.max_hp - 1
    assert combat.use_potion(enzo) == 1  # только до максимума


# ───────── групповые механики (§12) ─────────

def test_flee_survive_and_die(catalog):
    survive_rng = ScriptedRandom(ints=[8])  # 8 + DEX_eff(2) = 10 >= 10
    combat, (andryusha,), _ = make_combat(catalog, ["andryusha"], ["goblin"], survive_rng)
    assert combat.attempt_flee(andryusha) is True and andryusha.escaped

    die_rng = ScriptedRandom(ints=[5])  # 5 + 2 = 7 < 10
    combat2, (andr2,), _ = make_combat(catalog, ["andryusha"], ["goblin"], die_rng)
    assert combat2.attempt_flee(andr2) is False and andr2.dead


def test_intimidate_requires_str_superiority(catalog):
    # Арсельдор (STR 3) против гоблина (STR 3): 3 > 3 неверно -> недоступно
    rng = ScriptedRandom()
    combat, (arseldor,), _ = make_combat(catalog, ["arseldor"], ["goblin"], rng)
    res = combat.intimidate(arseldor, "enemy")
    assert not res.available


def test_intimidate_success_routs_enemies(catalog):
    # Андрюша (STR 12) > гоблин (STR 3); атака высокая, защита низкая -> успех -> побег врага
    rng = ScriptedRandom(ints=[20, 1, 3])  # atk d20=20, def d20=1, затем побег гоблина d20=3
    combat, (andryusha,), (goblin,) = make_combat(catalog, ["andryusha"], ["goblin"], rng)
    res = combat.intimidate(andryusha, "enemy")
    assert res.available and res.success
    # гоблин: 3 + DEX_eff(4) = 7 < 10 -> гибнет при побеге
    assert goblin.dead


def test_special_mechanic_once_per_combat(catalog):
    rng = ScriptedRandom(ints=[20, 1])
    combat, (andryusha,), (goblin,) = make_combat(catalog, ["andryusha"], ["goblin"], rng)
    combat.negotiate(andryusha, "enemy")
    second = combat.intimidate(andryusha, "enemy")
    assert not second.available  # уже применяли спец. механику


def test_negotiation_ends_combat(catalog):
    rng = ScriptedRandom(ints=[20, 1])
    combat, (andryusha,), (goblin,) = make_combat(catalog, ["andryusha"], ["goblin"], rng)
    res = combat.negotiate(andryusha, "enemy")
    assert res.success and combat.is_over() and combat.finished_by_negotiation


def test_failed_mechanic_applies_morale_debuff(catalog):
    # atk низкий, def высокий -> провал -> дебафф морали на сторону инициатора
    rng = ScriptedRandom(ints=[1, 20])
    combat, (andryusha,), (goblin,) = make_combat(catalog, ["andryusha"], ["goblin"], rng)
    res = combat.negotiate(andryusha, "enemy")
    assert not res.success
    from grokhanika.rules.effects import roll_modifier
    assert roll_modifier(andryusha.active_effects, attack=True) == -2
    assert roll_modifier(andryusha.active_effects, attack=False) == 0
