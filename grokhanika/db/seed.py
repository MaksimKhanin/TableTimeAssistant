"""Сид-данные: каталог снаряжения, 4 игровых персонажа и демо-существа.

Числа взяты из манифеста §14–§15. Источник истины — формулы (§3); карточки
персонажей в §15 содержат арифметические опечатки в «Физ.защите», поэтому здесь
заданы только характеристики и снаряжение, а атрибуты считаются движком.
"""
from __future__ import annotations

from ..enums import (
    AbilityTrigger,
    ActionType,
    ActivationSource,
    EffectTarget,
    EffectTargetType,
    SourceType,
)
from .models import (
    Ability,
    Armor,
    Character,
    Creature,
    Effect,
    Instrument,
    Item,
    Skill,
    SpellBook,
    Weapon,
)


def _buff_ability(name: str, desc: str, effect: dict) -> Ability:
    return Ability(
        name=name, description=desc, trigger=AbilityTrigger.ACTIVE.value,
        once_per_combat=True, actions=[{"type": ActionType.BUFF_ALLIES.value, "effect": effect}],
    )


def _debuff_ability(name: str, desc: str, effect: dict) -> Ability:
    return Ability(
        name=name, description=desc, trigger=AbilityTrigger.ACTIVE.value,
        once_per_combat=True, actions=[{"type": ActionType.DEBUFF_ENEMIES.value, "effect": effect}],
    )


def _stat_eff(target: EffectTarget, modifier: int, source_type: SourceType, activation: ActivationSource, desc: str) -> Effect:
    return Effect(
        target_type=EffectTargetType.STAT.value,
        target=target.value,
        modifier=modifier,
        duration=0,
        source_type=source_type.value,
        activation_source=activation.value,
        is_stackable=True,
        description=desc,
    )


def _attr_eff(target: EffectTarget, modifier: int, source_type: SourceType, activation: ActivationSource, desc: str) -> Effect:
    return Effect(
        target_type=EffectTargetType.ATTR.value,
        target=target.value,
        modifier=modifier,
        duration=0,
        source_type=source_type.value,
        activation_source=activation.value,
        is_stackable=True,
        description=desc,
    )


def seed_all(session) -> dict:
    """Наполнить БД и вернуть словарь ключ→карточка."""
    cat: dict = {}

    # ───────── оружие (§14) ─────────
    cat["dagger"] = Weapon(name="Кинжал", damage_dice="1d6", price=5)
    cat["short_sword"] = Weapon(
        name="Короткий меч", damage_dice="1d8", str_requirement=5, price=10,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -1, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Короткий меч: DEX -1")],
    )
    cat["greataxe"] = Weapon(
        name="Двуручный топор", damage_dice="1d10", str_requirement=7, price=8,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Двуручный топор: DEX -2")],
    )
    cat["staff"] = Weapon(
        name="Посох", damage_dice="1d4", price=5,
        effects=[_stat_eff(EffectTarget.WISDOM, 2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Посох: WIS +2")],
    )
    cat["bow"] = Weapon(
        name="Лук", damage_dice="1d8", dex_requirement=7, price=8, is_ranged=True,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Лук: DEX +2")],
    )
    cat["crossbow"] = Weapon(
        name="Арбалет", damage_dice="1d8", str_requirement=7, price=10, is_ranged=True,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Арбалет: DEX +2")],
    )

    # ───────── броня (§14) ─────────
    cat["leather"] = Armor(name="Кожаная броня", phys_def_bonus=1, price=8)
    cat["chainmail"] = Armor(
        name="Кольчуга", phys_def_bonus=2, str_requirement=5, price=12,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -1, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Кольчуга: DEX -1")],
    )
    cat["plate"] = Armor(
        name="Латный доспех", phys_def_bonus=3, str_requirement=7, price=15,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -3, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Латный доспех: DEX -3")],
    )
    cat["mage_robes"] = Armor(
        name="Одеяния мага", phys_def_bonus=0, price=8,
        effects=[_stat_eff(EffectTarget.WISDOM, 2, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Одеяния мага: WIS +2")],
    )

    # ───────── зелья (§14) ─────────
    cat["small_heal"] = Item(name="Малое зелье лечения", heal_dice="1d4", price=7, is_consumable=True)
    cat["heal"] = Item(name="Зелье лечения", heal_dice="2d4", price=10, is_consumable=True)
    cat["big_heal"] = Item(name="Большое зелье лечения", heal_dice="3d4", price=15, is_consumable=True)

    # ───────── магические предметы (§14) ─────────
    cat["luck_talisman"] = Item(
        name="Талисман удачи", price=10,
        effects=[_attr_eff(EffectTarget.ALL_D20_ROLLS, 2, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Талисман удачи: +2 ко всем d20")],
    )
    cat["magic_arrows"] = Item(
        name="Магические стрелы", price=5,
        effects=[_attr_eff(EffectTarget.PHYS_DAMAGE, 2, SourceType.ITEM, ActivationSource.IN_INVENTORY_RANGED, "Магические стрелы: +2 к урону (нужен лук/арбалет)")],
    )
    cat["wooden_shield"] = Item(
        name="Деревянный щит", price=7,
        effects=[
            _attr_eff(EffectTarget.PHYS_DEFENSE, 1, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Деревянный щит: +1 физ.защ."),
            _stat_eff(EffectTarget.DEXTERITY, -1, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Деревянный щит: DEX -1"),
        ],
    )
    # Уникальный щит с теми же характеристиками, что у деревянного, но дающий
    # пассивный навык «Бастион», пока лежит в инвентаре (grants_skill — ниже).
    cat["improdor_defender"] = Item(
        name="Защитник Импродора", price=7, is_unique=True,
        description="Уникальный щит: те же характеристики, что у деревянного, плюс навык «Бастион».",
        effects=[
            _attr_eff(EffectTarget.PHYS_DEFENSE, 1, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Защитник Импродора: +1 физ.защ."),
            _stat_eff(EffectTarget.DEXTERITY, -1, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Защитник Импродора: DEX -1"),
        ],
    )
    cat["vitality_amulet"] = Item(
        name="Амулет живучести", price=10,
        effects=[_attr_eff(EffectTarget.HP, 5, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Амулет живучести: +5 HP")],
    )

    # ───────── инструменты: предметы, дающие навык, пока в инвентаре (§6, §10) ─────────
    # Сам навык — отдельная сущность Skill (см. ниже); инструмент лишь даёт к нему
    # доступ, пока лежит в инвентаре. Связь grants_skill проставляется после создания
    # навыков. Инструмент покупается и продаётся (в отличие от навыка).
    cat["inspiring_lute"] = Instrument(
        name="Лютня вдохновения", description="Даёт навык «Песнь храбрости», пока в инвентаре", price=12,
    )
    cat["war_drum"] = Instrument(
        name="Барабан войны", description="Даёт навык «Гром деморализации», пока в инвентаре", price=12,
    )

    # ───────── тома магии (§14) ─────────
    cat["tome_ray"] = SpellBook(
        name="Том «Магический луч»", spell_name="Магический луч",
        damage_dice="1d10", difficulty=8, attack_stat="wisdom", price=7,
    )
    cat["tome_arrows"] = SpellBook(
        name="Том «Магические стрелы»", spell_name="Магические стрелы",
        damage_dice="4d4", difficulty=10, attack_stat="wisdom", price=7,
    )

    # ───────── навыки (механика тома/лютни, но вне инвентаря, не продаются) ─────────
    # Активный навык-заклинание (как том): кастует залп магических стрел.
    cat["skill_magic_arrows"] = Skill(
        name="Навык «Магические стрелы»",
        description="Выучен из тома. Постоянно: персонаж кастует залп магических стрел.",
        is_passive=False, price=12,
        spell_name="Магические стрелы", damage_dice="4d4", difficulty=10, attack_stat="wisdom",
    )
    # Том «Магические стрелы» при прочтении даёт этот навык (купил → прочитал → выучил).
    cat["tome_arrows"].teaches_skill = cat["skill_magic_arrows"]

    # Активный навык-способность (как у лютни): баффает всю партию. Этот навык
    # даёт лютня, пока лежит в инвентаре (grants_skill ниже).
    cat["skill_battle_song"] = Skill(
        name="Навык «Песнь храбрости»",
        description="Активный навык: на своём ходу воодушевляет всю партию.",
        is_passive=False, price=12,
        abilities=[
            _buff_ability(
                "Песнь храбрости", "Бафф всех сопартийцев: +2 ко всем d20 на 3 раунда",
                {
                    "target_type": EffectTargetType.ATTR.value,
                    "target": EffectTarget.ALL_D20_ROLLS.value,
                    "modifier": 2, "duration": 3, "source_type": SourceType.ITEM.value,
                    "description": "Воодушевление: +2 ко всем d20",
                },
            )
        ],
    )
    # Навык барабана: дебаффает всех врагов. Даёт барабан войны, пока в инвентаре.
    cat["skill_war_cry"] = Skill(
        name="Навык «Гром деморализации»",
        description="Активный навык: на своём ходу деморализует всех врагов.",
        is_passive=False, price=12,
        abilities=[
            _debuff_ability(
                "Гром деморализации", "Дебафф всех врагов: -2 к броскам атаки на 3 раунда",
                {
                    "target_type": EffectTargetType.ATTR.value,
                    "target": EffectTarget.ALL_ATTACK_ROLLS.value,
                    "modifier": -2, "duration": 3, "source_type": SourceType.ITEM.value,
                    "description": "Деморализация: -2 к атакам",
                },
            )
        ],
    )
    # Инструменты дают эти навыки, пока находятся в инвентаре носителя.
    cat["inspiring_lute"].grants_skill = cat["skill_battle_song"]
    cat["war_drum"].grants_skill = cat["skill_war_cry"]
    # Пассивный навык «Бастион»: держит строй (taunt). Несёт маркер-эффект BASTION;
    # пока носитель жив, одиночные атаки врага обязаны целиться в него.
    cat["skill_bastion"] = Skill(
        name="Навык «Бастион»",
        description="Пассивный навык: пока носитель жив, враг не может одиночной атакой "
                    "выбрать другую цель — сначала нужно убить всех носителей Бастиона.",
        is_passive=True, price=15,
        effects=[
            _attr_eff(EffectTarget.BASTION, 0, SourceType.ITEM, ActivationSource.IN_INVENTORY,
                      "Бастион: держит строй (taunt)"),
        ],
    )
    # «Защитник Импродора» даёт навык «Бастион», пока лежит в инвентаре.
    cat["improdor_defender"].grants_skill = cat["skill_bastion"]

    # Пассивный навык: постоянные эффекты, всегда активны (для демонстрации/витрины).
    cat["skill_iron_skin"] = Skill(
        name="Навык «Железная кожа»",
        description="Пассивный навык: постоянно +2 к физической защите.",
        is_passive=True, price=10,
        effects=[
            _attr_eff(EffectTarget.PHYS_DEFENSE, 2, SourceType.ITEM, ActivationSource.IN_INVENTORY,
                      "Железная кожа: +2 к физзащите (пассивный навык)"),
        ],
    )

    # ───────── игровые персонажи (§15) ─────────
    cat["enzo"] = Character(
        name="Энцо", description="Плут / Разбойник", is_player=True,
        base_strength=3, base_dexterity=12, base_wisdom=5, base_charisma=8, money=0,
        equipped_weapon=cat["dagger"], equipped_armor=cat["leather"],
        inventory=[cat["small_heal"], cat["luck_talisman"]],
    )
    cat["andryusha"] = Character(
        name="Андрюша", description="Воин", is_player=True,
        base_strength=12, base_dexterity=5, base_wisdom=3, base_charisma=5, money=1,
        # «Защитник Импродора» вместо деревянного щита: те же характеристики + навык «Бастион»
        inventory=[cat["improdor_defender"]],
        equipped_weapon=cat["short_sword"], equipped_armor=cat["chainmail"],
    )
    cat["salli"] = Character(
        name="Салли", description="Следопыт / Лучник", is_player=True,
        base_strength=5, base_dexterity=10, base_wisdom=7, base_charisma=3, money=2,
        equipped_weapon=cat["bow"], equipped_armor=cat["leather"],
        # лютня — предмет: даёт навык «Песнь храбрости», пока лежит в инвентаре
        inventory=[cat["small_heal"], cat["magic_arrows"], cat["inspiring_lute"]],
    )
    cat["arseldor"] = Character(
        name="Арсельдор", description="Маг", is_player=True,
        base_strength=3, base_dexterity=3, base_wisdom=14, base_charisma=5, money=0,
        equipped_weapon=cat["staff"], equipped_armor=cat["mage_robes"],
        inventory=[cat["vitality_amulet"]],
        # прочитал том «Магические стрелы» → выучил навык (том больше не в инвентаре)
        skills=[cat["skill_magic_arrows"]],
    )

    # ───────── демо-существа с уникальными способностями ─────────
    cat["goblin"] = Creature(
        name="Гоблин", description="Мелкий приспешник", is_sentient=True,
        hp=8, dexterity=4, phys_defense=8, mag_defense=2, mental_defense=6,
        phys_damage_dice="1d6", strength=3, charisma=2, wisdom=2,
    )
    cat["assassin"] = Creature(
        name="Теневой убийца", description="Бьёт насмерть", is_unique=True, is_sentient=True,
        hp=18, dexterity=10, phys_defense=12, mag_defense=4, mental_defense=8,
        phys_damage_dice="1d8", strength=6, charisma=4, wisdom=4,
        abilities=[
            Ability(
                name="Удар в сердце", description="Шанс мгновенно убить при попадании",
                trigger=AbilityTrigger.ON_HIT.value, chance=0.25, once_per_combat=False,
                condition={"target_is_sentient": True},
                actions=[{"type": ActionType.INSTAKILL.value, "chance": 1.0}],
            )
        ],
    )

    session.add_all(list(cat.values()))
    session.flush()  # назначаем id (нужно для ссылки призыва)

    cat["necromancer"] = Creature(
        name="Некромант", description="Поднимает приспешников", is_unique=True, is_sentient=True,
        hp=22, dexterity=6, phys_defense=10, mag_defense=6, mental_defense=9,
        phys_damage_dice="1d6", strength=4, charisma=6, wisdom=8,
        abilities=[
            Ability(
                name="Зов мертвецов", description="В начале боя призывает двух гоблинов",
                trigger=AbilityTrigger.ON_COMBAT_START.value, once_per_combat=True,
                actions=[{"type": ActionType.SUMMON.value, "creature_id": cat["goblin"].id, "count": 2}],
            ),
            _debuff_ability(
                "Леденящий взор", "Дебафф всех врагов: -2 к броскам атаки на 3 раунда",
                {
                    "target_type": EffectTargetType.ATTR.value,
                    "target": EffectTarget.ALL_ATTACK_ROLLS.value,
                    "modifier": -2, "duration": 3, "source_type": SourceType.SPELL.value,
                    "description": "Леденящий взор: -2 к атакам",
                },
            ),
        ],
    )
    session.add(cat["necromancer"])
    session.commit()
    return cat
