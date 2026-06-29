"""Проверка вычисляемых атрибутов против карточек персонажей (манифест §15).

Источник истины — формулы §3. Значения «Физ.защиты» взяты по формуле
(5 + DEX_eff//2 + armor + эффекты), т.к. в §15 у трёх персонажей там
арифметические опечатки (Энцо 11, Салли 13, Арсельдор 5 вместо 12/12/6).
"""
from grokhanika.engine.combatant import Combatant

# имя → ожидаемые (формульные) атрибуты
EXPECTED = {
    "enzo": dict(
        dex_eff=12, wis_eff=5, max_hp=18, phys_defense=12, mag_defense=2,
        mental_defense=9, phys_attack_bonus=6, mag_attack_bonus=2,
        phys_damage_dice="1d6", phys_damage_bonus=1,
    ),
    "andryusha": dict(
        dex_eff=2, wis_eff=3, max_hp=27, phys_defense=9, mag_defense=1,
        mental_defense=7, phys_attack_bonus=1, mag_attack_bonus=1,
        phys_damage_dice="1d8", phys_damage_bonus=6,
    ),
    "salli": dict(
        dex_eff=12, wis_eff=7, max_hp=20, phys_defense=12, mag_defense=3,
        mental_defense=6, phys_attack_bonus=6, mag_attack_bonus=3,
        phys_damage_dice="1d8", phys_damage_bonus=4,  # 5//2 + 2 (маг. стрелы при луке)
    ),
    "arseldor": dict(
        dex_eff=3, wis_eff=18, max_hp=23, phys_defense=6, mag_defense=9,
        mental_defense=7, phys_attack_bonus=1, mag_attack_bonus=9,
        phys_damage_dice="1d4", phys_damage_bonus=1,
    ),
}


def test_character_sheets(catalog):
    for key, expected in EXPECTED.items():
        c = Combatant(catalog[key], side="party")
        for attr_name, want in expected.items():
            got = getattr(c, attr_name)
            assert got == want, f"{key}.{attr_name}: ожидалось {want}, получено {got}"


def test_current_hp_defaults_to_max(catalog):
    enzo = Combatant(catalog["enzo"], side="party")
    assert enzo.current_hp == enzo.max_hp == 18


def test_magic_arrows_inactive_without_ranged_weapon(catalog):
    # У Энцо кинжал (не дальнобойное) — даже будь у него стрелы, бонус неактивен.
    enzo = Combatant(catalog["enzo"], side="party")
    assert enzo.phys_damage_bonus == 1  # только STR//2, без +2 за стрелы


def test_amulet_adds_hp_via_attr_effect(catalog):
    # Арсельдор: 15 + STR(3) + 5 (амулет) = 23
    arseldor = Combatant(catalog["arseldor"], side="party")
    assert arseldor.max_hp == 23
