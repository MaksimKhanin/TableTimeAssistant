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
    Scroll,
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
    cat["dagger"] = Weapon(
        name="Кинжал", description="Лёгкий клинок для скрытного удара — прост в обращении и смертоносен вблизи.",
        damage_dice="1d6", price=5,
    )
    cat["short_sword"] = Weapon(
        name="Короткий меч", description="Надёжный клинок на все случаи. Чуть тяжелее кинжала, немного сковывает реакцию.",
        damage_dice="1d8", str_requirement=5, price=10,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -1, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Короткий меч: DEX -1")],
    )
    cat["greataxe"] = Weapon(
        name="Двуручный топор", description="Огромный двуручный топор, сносящий врага с ног. Требует богатырской силы.",
        damage_dice="1d10", str_requirement=7, price=8,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Двуручный топор: DEX -2")],
    )
    cat["staff"] = Weapon(
        name="Посох", description="Деревянный жезл мага — усиливает мудрость и служит оружием ближнего боя.",
        damage_dice="1d4", price=5,
        effects=[_stat_eff(EffectTarget.WISDOM, 2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Посох: WIS +2")],
    )
    cat["bow"] = Weapon(
        name="Лук", description="Дальнобойное оружие охотника: точный выстрел издалека требует развитой ловкости.",
        damage_dice="1d8", dex_requirement=7, price=8, is_ranged=True,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Лук: DEX +2")],
    )
    cat["crossbow"] = Weapon(
        name="Арбалет", description="Мощный самострел, пробивающий лёгкие доспехи. Нужна сила, чтобы взводить тетиву.",
        damage_dice="1d8", str_requirement=7, price=10, is_ranged=True,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Арбалет: DEX +2")],
    )
    # Уникальный лук: те же характеристики, что у обычного, но самонаводящиеся
    # стрелы игнорируют Бастион — можно бить любую одиночную цель.
    cat["homing_bow"] = Weapon(
        name="Лук с самонаводящимися стрелами", damage_dice="1d8", dex_requirement=7,
        price=8, is_ranged=True, is_unique=True,
        description="Самонаводящиеся стрелы игнорируют Бастион и бьют любую цель.",
        effects=[
            _stat_eff(EffectTarget.DEXTERITY, 2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON,
                      "Лук с самонаведением: DEX +2"),
            _attr_eff(EffectTarget.IGNORE_BASTION, 0, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON,
                      "Самонаводящиеся стрелы: игнорируют Бастион"),
        ],
    )

    # ───────── дополнительное оружие ─────────
    cat["spear"] = Weapon(
        name="Копьё", description="Длинное древковое оружие — хороший баланс досягаемости и урона.",
        damage_dice="1d8", str_requirement=4, price=6,
    )
    cat["club"] = Weapon(
        name="Дубина", description="Грубое ударное оружие из дерева — дёшево, просто и сердито.",
        damage_dice="1d6", price=3,
    )
    cat["battle_axe"] = Weapon(
        name="Боевой топор", description="Надёжный топор воина — рубит щиты и пробивает лёгкую броню.",
        damage_dice="1d8", str_requirement=5, price=7,
    )
    cat["hunting_knife"] = Weapon(
        name="Охотничий нож", description="Острый нож следопыта — удобен и для охоты, и для поединка.",
        damage_dice="1d6", dex_requirement=5, price=4,
    )
    cat["rusty_sword"] = Weapon(
        name="Ржавый меч", description="Потрёпанный клинок с ржавчиной — дешёвый трофей с павшего врага.",
        damage_dice="1d6", price=2,
    )
    cat["halberd"] = Weapon(
        name="Алебарда", description="Тяжёлое двуручное оружие стражников — топор и копьё в одном.",
        damage_dice="1d10", str_requirement=8, price=12,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -1, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Алебарда: DEX -1")],
    )
    cat["magic_staff"] = Weapon(
        name="Магический посох", description="Посох, напитанный магией, — значительно усиливает заклинания и мудрость.",
        damage_dice="1d6", price=15,
        effects=[_stat_eff(EffectTarget.WISDOM, 3, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Магический посох: WIS +3")],
    )
    cat["short_bow"] = Weapon(
        name="Короткий лук", description="Лёгкий охотничий лук — меньше мощи, зато требует меньше ловкости.",
        damage_dice="1d6", dex_requirement=5, price=5, is_ranged=True,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 1, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Короткий лук: DEX +1")],
    )

    # ───────── броня (§14) ─────────
    cat["leather"] = Armor(
        name="Кожаная броня", description="Дублёная кожа не скует движений, но от серьёзных ударов не спасёт.",
        phys_def_bonus=1, price=8,
    )
    cat["chainmail"] = Armor(
        name="Кольчуга", description="Сотни стальных колец защищают от клинков, но сковывают ловкость воина.",
        phys_def_bonus=2, str_requirement=5, price=12,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -1, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Кольчуга: DEX -1")],
    )
    cat["plate"] = Armor(
        name="Латный доспех", description="Цельный стальной доспех — максимальная защита ценой резкого снижения манёвренности.",
        phys_def_bonus=3, str_requirement=7, price=15,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -3, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Латный доспех: DEX -3")],
    )
    cat["mage_robes"] = Armor(
        name="Одеяния мага", description="Зачарованные мантии, концентрирующие магическую силу и усиливающие мудрость чародея.",
        phys_def_bonus=0, price=8,
        effects=[_stat_eff(EffectTarget.WISDOM, 2, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Одеяния мага: WIS +2")],
    )

    # ───────── дополнительная броня ─────────
    cat["padded_jacket"] = Armor(
        name="Стёганая куртка", description="Простёганная ткань смягчает удары — доступна каждому крестьянину.",
        phys_def_bonus=1, price=4,
    )
    cat["tattered_leather"] = Armor(
        name="Рваная кожа", description="Обрывки кожаной брони — почти ничего не стоит, но лучше, чем ничего.",
        phys_def_bonus=1, price=1,
    )

    # ───────── зелья (§14) ─────────
    cat["small_heal"] = Item(
        name="Малое зелье лечения", description="Маленький пузырёк зелья — быстро затягивает незначительные порезы и ссадины.",
        heal_dice="1d4", price=7, is_consumable=True,
    )
    cat["heal"] = Item(
        name="Зелье лечения", description="Добротное зелье — возвращает силы после серьёзных боевых ранений.",
        heal_dice="2d4", price=10, is_consumable=True,
    )
    cat["big_heal"] = Item(
        name="Большое зелье лечения", description="Мощный эликсир восстановления, способный поднять воина даже с порога смерти.",
        heal_dice="3d4", price=15, is_consumable=True,
    )

    # ───────── магические предметы (§14) ─────────
    cat["luck_talisman"] = Item(
        name="Талисман удачи", description="Зачарованный амулет с клевером — судьба благосклоннее к носителю во всех бросках.",
        price=10,
        effects=[_attr_eff(EffectTarget.ALL_D20_ROLLS, 2, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Талисман удачи: +2 ко всем d20")],
    )
    cat["magic_arrows"] = Item(
        name="Магические стрелы", description="Зачарованные стрелы наносят дополнительный урон при стрельбе из лука или арбалета.",
        price=5,
        effects=[_attr_eff(EffectTarget.PHYS_DAMAGE, 2, SourceType.ITEM, ActivationSource.IN_INVENTORY_RANGED, "Магические стрелы: +2 к урону (нужен лук/арбалет)")],
    )
    cat["wooden_shield"] = Item(
        name="Деревянный щит", description="Прочный деревянный щит останавливает удары, но немного сковывает ловкость владельца.",
        price=7,
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
        name="Амулет живучести", description="Рубиновый амулет, укрепляющий жизненные силы и расширяющий запас здоровья носителя.",
        price=10,
        effects=[_attr_eff(EffectTarget.HP, 5, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Амулет живучести: +5 HP")],
    )

    cat["bandages"] = Item(
        name="Бинты", description="Тряпичные бинты — бедняцкая замена зелью лечения, годится в крайнем случае.",
        heal_dice="1d4", price=3, is_consumable=True,
    )
    cat["battle_shield"] = Item(
        name="Боевой щит", description="Стальной щит воина — надёжно защищает, но сильно сковывает движения.",
        price=12,
        effects=[
            _attr_eff(EffectTarget.PHYS_DEFENSE, 2, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Боевой щит: +2 физ.защ."),
            _stat_eff(EffectTarget.DEXTERITY, -2, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Боевой щит: DEX -2"),
        ],
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
        name="Том «Магический луч»", description="Фолиант с заклинанием концентрированного разряда — бьёт одну цель мощным лучом силы.",
        spell_name="Магический луч",
        damage_dice="1d10", difficulty=8, attack_stat="wisdom", price=7,
    )
    cat["tome_arrows"] = SpellBook(
        name="Том «Магические стрелы»", description="Том залпового заклинания. Прочитав однажды, персонаж выучивает навык навсегда.",
        spell_name="Магические стрелы",
        damage_dice="4d4", difficulty=10, attack_stat="wisdom", price=7,
    )

    # ───────── свитки (одноразовые заклинания) ─────────
    cat["scroll_fireball"] = Scroll(
        name="Свиток «Огненный шар»",
        description="Одноразовый свиток: накрывает группу врагов взрывом огня.",
        spell_name="Огненный шар", damage_dice="2d6", difficulty=9, attack_stat="wisdom", price=8,
    )
    cat["scroll_ice_arrow"] = Scroll(
        name="Свиток «Ледяная стрела»",
        description="Одноразовый свиток: пронизывает единственную цель стрелой льда.",
        spell_name="Ледяная стрела", damage_dice="1d10", difficulty=8, attack_stat="wisdom", price=6,
    )
    cat["scroll_heal"] = Scroll(
        name="Свиток «Исцеление»",
        description="Одноразовый свиток: восстанавливает здоровье союзника силой света.",
        spell_name="Исцеление", heal_dice="2d4", difficulty=7, attack_stat="wisdom", price=6,
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
        # лютня перешла к Энцо: пока она в его инвентаре, у него навык «Песнь храбрости»
        inventory=[cat["small_heal"], cat["luck_talisman"], cat["inspiring_lute"]],
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
        # уникальный лук с самонаведением: те же характеристики, но игнорирует Бастион
        equipped_weapon=cat["homing_bow"], equipped_armor=cat["leather"],
        inventory=[cat["small_heal"], cat["magic_arrows"]],
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

    # ───────── архетипы существ ─────────

    # ── обычные люди ──
    cat["peasant"] = Creature(
        name="Крестьянин", description="Мирный житель деревни с вилами. Лёгкая цель, но в толпе опасен.",
        is_sentient=True,
        hp=5, dexterity=3, phys_defense=6, mag_defense=1, mental_defense=5,
        phys_damage_dice="1d4", strength=2, charisma=2, wisdom=2,
    )
    cat["townsperson"] = Creature(
        name="Горожанин", description="Городской житель, способный постоять за себя. Можно запугать или убедить.",
        is_sentient=True,
        hp=6, dexterity=4, phys_defense=7, mag_defense=2, mental_defense=6,
        phys_damage_dice="1d4", strength=3, charisma=4, wisdom=3,
    )
    cat["peasant_mob"] = Creature(
        name="Толпа крестьян", description="Разозлённая толпа с вилами и факелами. Слаба поодиночке, но сметает всё скопом.",
        is_sentient=True,
        hp=25, dexterity=2, phys_defense=5, mag_defense=1, mental_defense=4,
        phys_damage_dice="2d6", strength=4, charisma=1, wisdom=1,
    )
    cat["city_mob"] = Creature(
        name="Толпа горожан", description="Разъярённые горожане — непредсказуемы и опасны числом, можно утихомирить речью.",
        is_sentient=True,
        hp=20, dexterity=3, phys_defense=6, mag_defense=2, mental_defense=5,
        phys_damage_dice="1d8", strength=3, charisma=2, wisdom=2,
    )

    # ── стражники и воины ──
    cat["city_guard"] = Creature(
        name="Городской стражник", description="Стражник городских ворот — хорошо обучен и действует по уставу.",
        is_sentient=True,
        hp=12, dexterity=5, phys_defense=10, mag_defense=3, mental_defense=7,
        phys_damage_dice="1d8", strength=6, charisma=4, wisdom=4,
    )
    cat["bandit"] = Creature(
        name="Бандит", description="Лесной разбойник, промышляющий грабежом. Беспощаден, но сдаётся при превосходстве.",
        is_sentient=True,
        hp=10, dexterity=6, phys_defense=9, mag_defense=2, mental_defense=6,
        phys_damage_dice="1d8", strength=5, charisma=3, wisdom=3,
    )
    cat["highwayman"] = Creature(
        name="Разбойник с большой дороги", description="Быстрый и коварный: атакует из засады и метко стреляет из лука.",
        is_sentient=True,
        hp=10, dexterity=8, phys_defense=9, mag_defense=2, mental_defense=7,
        phys_damage_dice="1d8", strength=4, charisma=3, wisdom=3,
    )
    cat["mercenary"] = Creature(
        name="Наёмник", description="Опытный наёмный солдат — воюет за деньги, но профессионально и надёжно.",
        is_sentient=True,
        hp=14, dexterity=6, phys_defense=11, mag_defense=3, mental_defense=7,
        phys_damage_dice="1d8", strength=7, charisma=3, wisdom=3,
    )
    cat["knight"] = Creature(
        name="Рыцарь", description="Закованный в латы рыцарь — лидер отряда, вдохновляющий союзников боевым кличем.",
        is_sentient=True,
        hp=20, dexterity=4, phys_defense=14, mag_defense=4, mental_defense=9,
        phys_damage_dice="1d10", strength=9, charisma=6, wisdom=5,
        abilities=[
            _buff_ability(
                "Боевой клич", "Рыцарь воодушевляет союзников: +2 ко всем броскам на 3 раунда",
                {
                    "target_type": EffectTargetType.ATTR.value,
                    "target": EffectTarget.ALL_D20_ROLLS.value,
                    "modifier": 2, "duration": 3, "source_type": SourceType.ITEM.value,
                    "description": "Боевой клич: +2 ко всем броскам",
                },
            ),
        ],
    )
    cat["orc"] = Creature(
        name="Орк", description="Свирепый орк — прирождённый воин, живёт войной и умирает с оружием в руках.",
        is_sentient=True,
        hp=15, dexterity=5, phys_defense=10, mag_defense=3, mental_defense=7,
        phys_damage_dice="1d10", strength=8, charisma=3, wisdom=2,
    )

    # ── животные ──
    cat["wolf"] = Creature(
        name="Волк", description="Лесной хищник — быстр, чуток и опасен в одиночку.",
        is_sentient=False,
        hp=10, dexterity=7, phys_defense=9, mag_defense=1, mental_defense=5,
        phys_damage_dice="1d8", strength=5, charisma=1, wisdom=3,
    )
    cat["wolf_pack"] = Creature(
        name="Стая волков", description="Слаженная стая действует как единый организм, окружая и изматывая добычу.",
        is_sentient=False,
        hp=22, dexterity=6, phys_defense=8, mag_defense=1, mental_defense=4,
        phys_damage_dice="2d6", strength=5, charisma=1, wisdom=2,
    )
    cat["bear"] = Creature(
        name="Медведь", description="Огромный лесной медведь — медлительный, но обладает чудовищной силой удара.",
        is_sentient=False,
        hp=18, dexterity=5, phys_defense=11, mag_defense=2, mental_defense=6,
        phys_damage_dice="1d10", strength=9, charisma=1, wisdom=3,
    )
    cat["giant_rat"] = Creature(
        name="Гигантская крыса", description="Крупная болотная крыса с острыми зубами — чаще встречается группами.",
        is_sentient=False,
        hp=4, dexterity=6, phys_defense=6, mag_defense=1, mental_defense=3,
        phys_damage_dice="1d4", strength=2, charisma=1, wisdom=2,
    )
    cat["bat_swarm"] = Creature(
        name="Рой летучих мышей", description="Тучи острых зубов — почти невозможно поразить одним ударом, изматывает укусами.",
        is_sentient=False,
        hp=12, dexterity=8, phys_defense=7, mag_defense=1, mental_defense=3,
        phys_damage_dice="1d4", strength=1, charisma=1, wisdom=2,
    )

    # ── нежить ──
    cat["skeleton"] = Creature(
        name="Скелет", description="Оживлённые магией кости — не чувствует страха и боли, безмолвный исполнитель приказов.",
        is_sentient=False,
        hp=8, dexterity=5, phys_defense=8, mag_defense=2, mental_defense=15,
        phys_damage_dice="1d6", strength=4, charisma=1, wisdom=1,
    )
    cat["zombie"] = Creature(
        name="Зомби", description="Медлительный ходячий мертвец — крайне живучий, не реагирует на угрозы и боль.",
        is_sentient=False,
        hp=12, dexterity=2, phys_defense=9, mag_defense=3, mental_defense=15,
        phys_damage_dice="1d6", strength=6, charisma=1, wisdom=1,
    )
    cat["undead_horde"] = Creature(
        name="Толпа нежити", description="Волна ходячих мертвецов, сметающая всё на пути. Никакие угрозы их не остановят.",
        is_sentient=False,
        hp=30, dexterity=2, phys_defense=7, mag_defense=2, mental_defense=15,
        phys_damage_dice="2d6", strength=5, charisma=1, wisdom=1,
    )
    cat["ghost"] = Creature(
        name="Призрак", description="Неупокоенный дух — нематериален, почти недосягаем для оружия, сеет смертельный ужас.",
        is_sentient=False,
        hp=10, dexterity=8, phys_defense=16, mag_defense=10, mental_defense=8,
        phys_damage_dice="1d6", strength=2, charisma=3, wisdom=6,
        abilities=[
            _debuff_ability(
                "Смертельный ужас", "Вид призрака парализует врагов страхом: -2 к атакам на 3 раунда",
                {
                    "target_type": EffectTargetType.ATTR.value,
                    "target": EffectTarget.ALL_ATTACK_ROLLS.value,
                    "modifier": -2, "duration": 3, "source_type": SourceType.SPELL.value,
                    "description": "Смертельный ужас: -2 к атакам",
                },
            ),
        ],
    )
    cat["skeleton_archer"] = Creature(
        name="Скелет-лучник", description="Скелет с луком: стреляет без устали с дальней дистанции, пока его не уничтожат.",
        is_sentient=False,
        hp=7, dexterity=7, phys_defense=7, mag_defense=2, mental_defense=15,
        phys_damage_dice="1d8", strength=3, charisma=1, wisdom=1,
    )

    # ── прочие существа ──
    cat["ogre"] = Creature(
        name="Огр", description="Огромный тупоголовый огр — дикая сила, почти нет интеллекта, смертоносен в ближнем бою.",
        is_sentient=True,
        hp=25, dexterity=3, phys_defense=12, mag_defense=3, mental_defense=5,
        phys_damage_dice="1d12", strength=12, charisma=1, wisdom=1,
    )
    cat["troll"] = Creature(
        name="Тролль", description="Живучий тролль с грубой кожей. Говорят, мелкие раны затягиваются у него прямо в бою.",
        is_sentient=True,
        hp=20, dexterity=4, phys_defense=11, mag_defense=4, mental_defense=6,
        phys_damage_dice="1d10", strength=10, charisma=1, wisdom=2,
    )
    cat["kobold"] = Creature(
        name="Кобольд", description="Юркий ящероподобный кобольд — слаб в одиночку, но хитёр и любит засады.",
        is_sentient=True,
        hp=4, dexterity=7, phys_defense=7, mag_defense=2, mental_defense=5,
        phys_damage_dice="1d4", strength=2, charisma=2, wisdom=3,
    )
    cat["dark_priest"] = Creature(
        name="Жрец тьмы", description="Служитель тёмных богов, насылающий проклятия и лишающий врагов боевого духа.",
        is_sentient=True, is_unique=True,
        hp=16, dexterity=4, phys_defense=8, mag_defense=8, mental_defense=10,
        phys_damage_dice="1d4", strength=3, charisma=7, wisdom=10,
        abilities=[
            _debuff_ability(
                "Проклятие тьмы", "Жрец насылает проклятие: -2 к броскам атаки всех врагов на 3 раунда",
                {
                    "target_type": EffectTargetType.ATTR.value,
                    "target": EffectTarget.ALL_ATTACK_ROLLS.value,
                    "modifier": -2, "duration": 3, "source_type": SourceType.SPELL.value,
                    "description": "Проклятие тьмы: -2 к атакам",
                },
            ),
        ],
    )
    cat["merchant"] = Creature(
        name="Торговец", description="Мирный торговец — беззащитен в схватке, но щедро платит за охрану и сведения.",
        is_sentient=True,
        hp=6, dexterity=4, phys_defense=7, mag_defense=2, mental_defense=8,
        phys_damage_dice="1d4", strength=2, charisma=8, wisdom=6,
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
