"""Тесты навыков: механика как у тома/лютни, но вне инвентаря и без расхода."""
from grokhanika.db.models import Character, Effect, Skill
from grokhanika.engine import Combat, Combatant
from grokhanika.enums import (
    ActivationSource,
    EffectTarget,
    EffectTargetType,
    SourceType,
)
from grokhanika.rules.skills import LearnError, learn_from_tome

from .conftest import ScriptedRandom


# ───────────────────────── навык-заклинание (как том) ─────────────────────────


def test_casting_skill_is_a_spell_source_outside_inventory(catalog):
    arseldor = Combatant(catalog["arseldor"], "party")
    # навык даёт источник заклинания, но в инвентаре спелл-карриеров нет
    assert any(c.spell_name == "Магические стрелы" for c in arseldor.spell_carriers)
    assert not any(it.is_spell_carrier for it in arseldor.inventory)


def test_skill_spell_not_consumed_after_cast(catalog):
    arseldor = Combatant(catalog["arseldor"], "party")
    goblin = Combatant(catalog["goblin"], "enemy")
    skill_carrier = arseldor.spell_carriers[0]
    # активация d20=5 -> 5+маг.атака(9)=14 >= сл.10; спас d20=1 -> провал
    combat = Combat([arseldor, goblin], rng=ScriptedRandom(ints=[5, 1]))

    res = combat.cast_from_carrier(arseldor, goblin, skill_carrier.card_id)
    assert res is not None and res.activated
    # навык остаётся доступен — повторно кастуется (не расходуется, как свиток)
    assert any(c.card_id == skill_carrier.card_id for c in arseldor.spell_carriers)


# ───────────────────── предмет, дающий навык, пока в инвентаре (лютня) ─────────────────────


def test_item_grants_skill_while_in_inventory(catalog):
    # Лютня — предмет (её можно продать). Пока она в инвентаре Энцо,
    # Энцо владеет навыком «Песнь храбрости». Постоянных навыков у него нет.
    enzo = Combatant(catalog["enzo"], "party")
    assert any(spec.name == "Песнь храбрости" for spec in enzo.abilities)
    assert any(it.name == "Лютня вдохновения" for it in enzo.inventory)
    assert catalog["enzo"].skills == []


def test_ability_from_granted_skill_buffs_party(catalog):
    enzo = Combatant(catalog["enzo"], "party")
    andr = Combatant(catalog["andryusha"], "party")
    goblin = Combatant(catalog["goblin"], "enemy")
    combat = Combat([enzo, andr, goblin], rng=ScriptedRandom())

    combat.activate_ability(enzo, "Песнь храбрости")  # навык от лютни
    assert any(e.target == EffectTarget.ALL_D20_ROLLS.value for e in andr.temporary_effects)


def test_selling_item_removes_granted_skill(catalog, session):
    enzo_card = catalog["enzo"]
    enzo_card.inventory.remove(catalog["inspiring_lute"])  # «продал» лютню
    session.flush()
    enzo = Combatant(enzo_card, "party")
    assert not any(spec.name == "Песнь храбрости" for spec in enzo.abilities)


# ───────────────────────── пассивный навык (эффекты всегда активны) ─────────────────────────


def test_passive_skill_effect_always_active(catalog, session):
    skill = Skill(
        name="Тестовая стойкость", is_passive=True, price=5,
        effects=[
            Effect(
                target_type=EffectTargetType.ATTR.value,
                target=EffectTarget.PHYS_DEFENSE.value,
                modifier=3, duration=0,
                source_type=SourceType.ITEM.value,
                activation_source=ActivationSource.IN_INVENTORY.value,
                description="Тест: +3 физз.",
            )
        ],
    )
    stats = dict(base_strength=5, base_dexterity=4, base_wisdom=5, base_charisma=5)
    hero = Character(name="Подопытный", is_player=False, **stats)
    control = Character(name="Контроль", is_player=False, **stats)
    hero.skills.append(skill)
    session.add_all([skill, hero, control])
    session.flush()

    base = Combatant(control, "party")
    with_skill = Combatant(hero, "party")
    assert with_skill.phys_defense == base.phys_defense + 3


# ───────────────────────── обучение из тома (купил → прочитал → выучил) ─────────────────────────


def test_learn_from_tome_grants_skill_and_consumes_tome(catalog, session):
    arseldor = catalog["arseldor"]
    tome = catalog["tome_arrows"]
    arseldor.inventory.append(tome)
    session.flush()
    assert tome in arseldor.inventory

    learned = learn_from_tome(arseldor, tome)

    assert learned is catalog["skill_magic_arrows"]
    assert learned in arseldor.skills           # навык получен
    assert tome not in arseldor.inventory       # том прочитан и убран из инвентаря


def test_learn_from_tome_idempotent(catalog, session):
    salli = catalog["salli"]
    tome = catalog["tome_arrows"]
    learn_from_tome(salli, tome)
    learn_from_tome(salli, tome)  # повторно — без дублирования
    assert sum(1 for s in salli.skills if s is catalog["skill_magic_arrows"]) == 1


def test_learn_from_tome_without_skill_raises(catalog):
    # «Том Магический луч» никого не учит навыку
    try:
        learn_from_tome(catalog["arseldor"], catalog["tome_ray"])
        assert False, "ожидалась LearnError"
    except LearnError:
        pass
