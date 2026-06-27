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
    LoreEntry,
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

    cat["scimitar"] = Weapon(
        name="Ятаган", description="Изогнутый клинок конных воинов — быстрее прямого меча, усиливает ловкость.",
        damage_dice="1d8", dex_requirement=5, price=9,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 1, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Ятаган: DEX +1")],
    )
    cat["warhammer"] = Weapon(
        name="Боевой молот", description="Тяжёлый молот — медленен, но с одного удара проламывает любой шлем.",
        damage_dice="1d8", str_requirement=6, price=8,
    )
    cat["rapier"] = Weapon(
        name="Рапира", description="Тонкий клинок для точных выпадов — требует ловкости, но ранит стремительно.",
        damage_dice="1d6", dex_requirement=6, price=9,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 1, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Рапира: DEX +1")],
    )
    cat["sling"] = Weapon(
        name="Праща", description="Праща с камнями — дальнобойна и дёшева, оружие пастухов и нищих.",
        damage_dice="1d4", price=3, is_ranged=True,
    )
    cat["throwing_knives"] = Weapon(
        name="Метательные ножи", description="Связка острых ножей — в умелых руках летят раньше, чем враг успевает моргнуть.",
        damage_dice="1d4", dex_requirement=5, price=5, is_ranged=True,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 1, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Метательные ножи: DEX +1")],
    )
    cat["magic_dagger"] = Weapon(
        name="Магический кинжал", description="Уникальный зачарованный кинжал: лезвие само ищет щели в защите врага.",
        damage_dice="1d8", price=18, is_unique=True,
        effects=[_stat_eff(EffectTarget.WISDOM, 1, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Магический кинжал: WIS +1")],
    )
    cat["trident"] = Weapon(
        name="Трезубец", description="Трезубец морских разбойников — длинный и смертоносный, требует физической силы.",
        damage_dice="1d8", str_requirement=5, price=8,
    )
    cat["war_gauntlets"] = Weapon(
        name="Боевые рукавицы", description="Шипованные рукавицы — оружие бойца, который дерётся голыми руками.",
        damage_dice="1d6", price=9,
        effects=[_stat_eff(EffectTarget.STRENGTH, 1, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Боевые рукавицы: STR +1")],
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

    cat["scale_armor"] = Armor(
        name="Чешуйчатый доспех", description="Пластины чешуи на кожаной основе — лучше кольчуги, требует крепкого тела.",
        phys_def_bonus=2, str_requirement=5, price=11,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -1, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Чешуйчатый доспех: DEX -1")],
    )
    cat["enchanted_robes"] = Armor(
        name="Зачарованные одеяния", description="Одеяния высшего мага — тонкая ткань, пропитанная волшебством.",
        phys_def_bonus=0, price=12,
        effects=[_stat_eff(EffectTarget.WISDOM, 3, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Зачарованные одеяния: WIS +3")],
    )
    cat["berserker_armor"] = Armor(
        name="Доспех берсерка", description="Броня ярости в металле — даёт огромную силу и защиту ценой манёвренности.",
        phys_def_bonus=2, str_requirement=6, price=12,
        effects=[
            _stat_eff(EffectTarget.STRENGTH, 3, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Доспех берсерка: STR +3"),
            _stat_eff(EffectTarget.DEXTERITY, -3, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Доспех берсерка: DEX -3"),
        ],
    )
    cat["scout_armor"] = Armor(
        name="Лёгкий доспех разведчика", description="Не стесняет движений и добавляет манёвренности — идеален для лазутчиков.",
        phys_def_bonus=1, price=10,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 1, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Лёгкий доспех разведчика: DEX +1")],
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

    # ───────── дополнительные магические предметы ─────────
    cat["dex_gloves"] = Item(
        name="Перчатки ловкача", description="Перчатки из паучьего шёлка — чуть ускоряют реакцию и движения носителя.",
        price=8,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 1, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Перчатки ловкача: DEX +1")],
    )
    cat["protection_ring"] = Item(
        name="Кольцо защиты", description="Зачарованное кольцо с рунами — слабо, но неустанно отражает удары.",
        price=10,
        effects=[_attr_eff(EffectTarget.PHYS_DEFENSE, 1, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Кольцо защиты: +1 физ.защ.")],
    )
    cat["strength_belt"] = Item(
        name="Пояс силы", description="Кованый пояс, усиливающий мышечную силу носителя волшебством кузнеца.",
        price=12,
        effects=[_stat_eff(EffectTarget.STRENGTH, 2, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Пояс силы: STR +2")],
    )
    cat["wisdom_amulet"] = Item(
        name="Амулет мудрости", description="Серебряный амулет с лунным камнем — обостряет ум и магическую интуицию.",
        price=12,
        effects=[_stat_eff(EffectTarget.WISDOM, 2, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Амулет мудрости: WIS +2")],
    )
    cat["berserker_gauntlets"] = Item(
        name="Перчатки берсерка", description="Шипованные перчатки ярости: огромный прирост силы ценой разума и ловкости.",
        price=15,
        effects=[
            _stat_eff(EffectTarget.STRENGTH, 3, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Перчатки берсерка: STR +3"),
            _stat_eff(EffectTarget.WISDOM, -2, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Перчатки берсерка: WIS -2"),
            _stat_eff(EffectTarget.DEXTERITY, -1, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Перчатки берсерка: DEX -1"),
        ],
    )
    cat["shadow_boots"] = Item(
        name="Сапоги тени", description="Уникальные сапоги из тёмной кожи — владелец движется бесшумно и невероятно быстро.",
        price=14, is_unique=True,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 2, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Сапоги тени: DEX +2")],
    )
    cat["warrior_ring"] = Item(
        name="Перстень воина", description="Простой перстень — немного укрепляет удар и рукопожатие бойца.",
        price=7,
        effects=[_stat_eff(EffectTarget.STRENGTH, 1, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Перстень воина: STR +1")],
    )
    cat["fire_ring"] = Item(
        name="Кольцо огня", description="Уникальное кольцо с рубиновым пламенем — добавляет жар к каждому удару.",
        price=12, is_unique=True,
        effects=[_attr_eff(EffectTarget.PHYS_DAMAGE, 2, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Кольцо огня: +2 к физ.урону")],
    )
    cat["mage_focus"] = Item(
        name="Фокус мага", description="Хрустальный шар — концентрирует магию без посоха, усиливает мудрость чародея.",
        price=10,
        effects=[_stat_eff(EffectTarget.WISDOM, 2, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Фокус мага: WIS +2")],
    )
    cat["hp_crystal"] = Item(
        name="Кристалл жизни", description="Пульсирующий кристалл — расширяет запас сил, будто вдыхаешь горный воздух.",
        price=15,
        effects=[_attr_eff(EffectTarget.HP, 8, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Кристалл жизни: +8 HP")],
    )
    cat["charisma_medallion"] = Item(
        name="Медальон харизмы", description="Золотой медальон — окружающие инстинктивно проникаются уважением к носителю.",
        price=10,
        effects=[_stat_eff(EffectTarget.CHARISMA, 2, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Медальон харизмы: CHA +2")],
    )
    cat["wanderer_cloak"] = Item(
        name="Плащ странника", description="Уникальный плащ путника — скрывает силуэт и немного защищает от ударов.",
        price=18, is_unique=True,
        effects=[
            _stat_eff(EffectTarget.DEXTERITY, 1, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Плащ странника: DEX +1"),
            _attr_eff(EffectTarget.PHYS_DEFENSE, 1, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Плащ странника: +1 физ.защ."),
        ],
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

    cat["tome_fireball"] = SpellBook(
        name="Том «Огненный шар»",
        description="Том огненного взрыва. Основная цель — полный урон, все прочие враги получают AoE-взрыв.",
        spell_name="Огненный шар", damage_dice="2d6", aoe_damage_dice="1d6",
        difficulty=9, attack_stat="wisdom", price=15,
    )
    cat["tome_lightning"] = SpellBook(
        name="Том «Молния»",
        description="Фолиант молниеносного разряда — мощнейший одиночный удар природной магии.",
        spell_name="Молния", damage_dice="1d12", difficulty=10, attack_stat="wisdom", price=15,
    )
    cat["tome_frost_sphere"] = SpellBook(
        name="Том «Сфера холода»",
        description="Том ледяного заклинания — тяжёлый шар льда замораживает и ранит одну цель.",
        spell_name="Сфера холода", damage_dice="1d10", difficulty=9, attack_stat="wisdom", price=12,
    )

    # ───────── свитки (одноразовые заклинания) ─────────
    cat["scroll_fireball"] = Scroll(
        name="Свиток «Огненный шар»",
        description="Одноразовый свиток: взрыв огня. Основная цель — полный урон; все прочие враги — AoE-взрыв.",
        spell_name="Огненный шар", damage_dice="2d6", aoe_damage_dice="1d6",
        difficulty=9, attack_stat="wisdom", price=8,
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
    cat["scroll_lightning"] = Scroll(
        name="Свиток «Молния»",
        description="Одноразовый свиток: мощный разряд молнии бьёт одну цель с огромной силой.",
        spell_name="Молния", damage_dice="1d12", difficulty=10, attack_stat="wisdom", price=10,
    )
    cat["scroll_acid"] = Scroll(
        name="Свиток «Кислота»",
        description="Одноразовый свиток: кислотный плевок разъедает броню и плоть цели.",
        spell_name="Кислотный плевок", damage_dice="1d8", difficulty=7, attack_stat="wisdom", price=5,
    )
    cat["scroll_blinding_light"] = Scroll(
        name="Свиток «Слепящий свет»",
        description="Одноразовый свиток: ослепительная вспышка бьёт по чувствам и разуму цели.",
        spell_name="Слепящий свет", damage_dice="1d6", difficulty=7, attack_stat="wisdom", price=5,
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

    cat["skill_fireball"] = Skill(
        name="Навык «Огненный шар»",
        description="Выученный навык. Маг кастует взрыв: основная цель получает полный урон, все остальные враги — AoE-взрыв.",
        is_passive=False, price=18,
        spell_name="Огненный шар", damage_dice="2d6", aoe_damage_dice="1d6",
        difficulty=9, attack_stat="wisdom",
    )
    cat["tome_fireball"].teaches_skill = cat["skill_fireball"]

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
        name="Толпа крестьян", description="Минимум пять крестьян с вилами и факелами. Слабы поодиночке, но вместе ломают всё.",
        is_sentient=True,
        hp=35, dexterity=2, phys_defense=5, mag_defense=1, mental_defense=8,
        phys_damage_dice="3d4", strength=5, charisma=1, wisdom=1,
    )
    cat["city_mob"] = Creature(
        name="Толпа горожан", description="Пять-восемь разъярённых горожан — опасны числом, остановить словом крайне трудно.",
        is_sentient=True,
        hp=35, dexterity=3, phys_defense=6, mag_defense=2, mental_defense=9,
        phys_damage_dice="3d6", strength=5, charisma=2, wisdom=2,
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
        name="Стая волков", description="Пять-шесть волков, действующих как единый хищник: окружают, изматывают, добивают.",
        is_sentient=False,
        hp=40, dexterity=6, phys_defense=8, mag_defense=1, mental_defense=4,
        phys_damage_dice="3d8", strength=6, charisma=1, wisdom=2,
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
        name="Толпа нежити", description="Пять-семь ходячих мертвецов — неумолимая волна. Угрозы бесполезны, они не знают страха.",
        is_sentient=False,
        hp=50, dexterity=2, phys_defense=7, mag_defense=2, mental_defense=15,
        phys_damage_dice="4d6", strength=6, charisma=1, wisdom=1,
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

    # ── новые архетипы ──
    cat["pirate"] = Creature(
        name="Пират", description="Морской разбойник с саблей — быстр, безжалостен и привычен к ближней схватке.",
        is_sentient=True,
        hp=12, dexterity=7, phys_defense=9, mag_defense=2, mental_defense=6,
        phys_damage_dice="1d8", strength=5, charisma=3, wisdom=3,
    )
    cat["cultist"] = Creature(
        name="Адепт культа", description="Фанатик тёмного культа — слаб телом, но опасен верой и чёрной магией.",
        is_sentient=True,
        hp=8, dexterity=4, phys_defense=7, mag_defense=6, mental_defense=9,
        phys_damage_dice="1d4", strength=2, charisma=5, wisdom=7,
    )
    cat["bandit_leader"] = Creature(
        name="Главарь бандитов", description="Главарь шайки — опытный боец и командир, поднимающий боевой дух подельников.",
        is_sentient=True, is_unique=True,
        hp=15, dexterity=7, phys_defense=10, mag_defense=3, mental_defense=8,
        phys_damage_dice="1d8", strength=6, charisma=5, wisdom=4,
        abilities=[
            _buff_ability(
                "Командный рёв", "Главарь орёт на своих: +2 ко всем броскам союзников на 3 раунда",
                {
                    "target_type": EffectTargetType.ATTR.value,
                    "target": EffectTarget.ALL_D20_ROLLS.value,
                    "modifier": 2, "duration": 3, "source_type": SourceType.ITEM.value,
                    "description": "Командный рёв: +2 ко всем броскам",
                },
            ),
        ],
    )
    cat["guard_captain"] = Creature(
        name="Капитан стражи", description="Закалённый ветеран стражи — координирует оборону и воодушевляет отряд.",
        is_sentient=True, is_unique=True,
        hp=18, dexterity=5, phys_defense=12, mag_defense=4, mental_defense=9,
        phys_damage_dice="1d8", strength=7, charisma=6, wisdom=5,
        abilities=[
            _buff_ability(
                "Держать строй", "Капитан укрепляет дисциплину: +2 ко всем броскам стражников на 3 раунда",
                {
                    "target_type": EffectTargetType.ATTR.value,
                    "target": EffectTarget.ALL_D20_ROLLS.value,
                    "modifier": 2, "duration": 3, "source_type": SourceType.ITEM.value,
                    "description": "Держать строй: +2 ко всем броскам",
                },
            ),
        ],
    )
    cat["shaman"] = Creature(
        name="Шаман", description="Племенной шаман — связывает мир духов и живых, ослабляет врагов проклятием.",
        is_sentient=True,
        hp=12, dexterity=4, phys_defense=8, mag_defense=7, mental_defense=8,
        phys_damage_dice="1d4", strength=3, charisma=6, wisdom=9,
        abilities=[
            _debuff_ability(
                "Проклятие духов", "Шаман насылает духов: -2 к атакам всех врагов на 3 раунда",
                {
                    "target_type": EffectTargetType.ATTR.value,
                    "target": EffectTarget.ALL_ATTACK_ROLLS.value,
                    "modifier": -2, "duration": 3, "source_type": SourceType.SPELL.value,
                    "description": "Проклятие духов: -2 к атакам",
                },
            ),
        ],
    )
    cat["witch"] = Creature(
        name="Ведьма", description="Одинокая ведьма — владеет тёмными чарами и сглазом, опасна с расстояния.",
        is_sentient=True, is_unique=True,
        hp=14, dexterity=5, phys_defense=8, mag_defense=9, mental_defense=10,
        phys_damage_dice="1d4", strength=2, charisma=6, wisdom=11,
        abilities=[
            _debuff_ability(
                "Сглаз", "Ведьма насылает сглаз: -2 к броскам атаки всех врагов на 3 раунда",
                {
                    "target_type": EffectTargetType.ATTR.value,
                    "target": EffectTarget.ALL_ATTACK_ROLLS.value,
                    "modifier": -2, "duration": 3, "source_type": SourceType.SPELL.value,
                    "description": "Сглаз: -2 к атакам",
                },
            ),
        ],
    )
    cat["vampire"] = Creature(
        name="Вампир", description="Бессмертный вампир — неестественно быстр и силён, жаждет крови для исцеления.",
        is_sentient=True, is_unique=True,
        hp=20, dexterity=9, phys_defense=12, mag_defense=8, mental_defense=10,
        phys_damage_dice="1d8", strength=7, charisma=8, wisdom=6,
        abilities=[
            Ability(
                name="Кровавый укус", description="Шанс мгновенно убить смертного при попадании",
                trigger=AbilityTrigger.ON_HIT.value, chance=0.15, once_per_combat=False,
                condition={"target_is_sentient": True},
                actions=[{"type": ActionType.INSTAKILL.value, "chance": 1.0}],
            ),
        ],
    )
    cat["werewolf"] = Creature(
        name="Оборотень", description="Человек-волк в обличье зверя — первобытная ярость и недостижимая скорость.",
        is_sentient=True, is_unique=True,
        hp=22, dexterity=9, phys_defense=11, mag_defense=5, mental_defense=8,
        phys_damage_dice="1d10", strength=10, charisma=2, wisdom=3,
    )
    cat["stone_golem"] = Creature(
        name="Каменный голем", description="Магически оживлённый голем из камня — медленен, но практически неуязвим физически.",
        is_sentient=False,
        hp=35, dexterity=2, phys_defense=16, mag_defense=6, mental_defense=20,
        phys_damage_dice="1d10", strength=12, charisma=1, wisdom=1,
    )
    cat["demon"] = Creature(
        name="Демон", description="Исчадие тьмы с горящими глазами — запредельная сила и парализующий страх.",
        is_sentient=True, is_unique=True,
        hp=28, dexterity=7, phys_defense=13, mag_defense=12, mental_defense=12,
        phys_damage_dice="1d10", strength=10, charisma=8, wisdom=9,
        abilities=[
            _debuff_ability(
                "Аура ужаса", "Демон излучает ужас: -2 к броскам атаки всех врагов на 3 раунда",
                {
                    "target_type": EffectTargetType.ATTR.value,
                    "target": EffectTarget.ALL_ATTACK_ROLLS.value,
                    "modifier": -2, "duration": 3, "source_type": SourceType.SPELL.value,
                    "description": "Аура ужаса: -2 к атакам",
                },
            ),
        ],
    )
    cat["dragon"] = Creature(
        name="Дракон", description="Древний дракон — властелин неба, огня и страха. Самое опасное существо.",
        is_sentient=True, is_unique=True,
        hp=55, dexterity=6, phys_defense=16, mag_defense=14, mental_defense=13,
        phys_damage_dice="2d10", strength=14, charisma=10, wisdom=10,
        abilities=[
            _debuff_ability(
                "Огненное дыхание", "Дракон выдыхает пламя: -2 к атакам всех врагов на 3 раунда",
                {
                    "target_type": EffectTargetType.ATTR.value,
                    "target": EffectTarget.ALL_ATTACK_ROLLS.value,
                    "modifier": -2, "duration": 3, "source_type": SourceType.SPELL.value,
                    "description": "Огненное дыхание: -2 к атакам",
                },
            ),
        ],
    )

    # ───────── NPC и лор для приключения (RAG / ИИ-ГМ) ─────────
    # «Горожанин» и «Городской стражник» уже есть среди архетипов выше — здесь только
    # уникальный для сцен трактирщик и лор-записи мира (их нет в боевом каталоге).
    cat["npc_innkeeper"] = Creature(
        name="Трактирщик", description="Хозяин таверны: наливает эль, сдаёт комнаты и охотно "
        "делится новостями и сплетнями за пару монет.",
        is_sentient=True, hp=8, dexterity=3, phys_defense=9, mag_defense=2, mental_defense=6,
        phys_damage_dice="1d4", strength=4, charisma=7, wisdom=5,
    )

    cat["lore_world"] = LoreEntry(
        name="Мир Гроханика", category="history",
        description="Гроханика — суровый фэнтезийный край разрозненных городов-государств, "
        "тёмных лесов и древних руин. После падения Старой Короны земли держатся на торговых "
        "союзах, наёмных отрядах и хрупких перемириях между фракциями.",
    )
    cat["lore_improdor"] = LoreEntry(
        name="Импродор", category="location",
        description="Импродор — укреплённый торговый город на перекрёстке трактов, известный "
        "оружейными мастерскими и крепкой городской стражей. Здесь куётся легендарный «Защитник "
        "Импродора». Рынок шумит днём, а в тавернах у стен заключаются ночные сделки.",
    )
    cat["lore_velg"] = LoreEntry(
        name="Деревня Вельг", category="location",
        description="Вельг — небольшая деревня на опушке Чернолесья. Живёт пашней и охотой, "
        "страдает от набегов гоблинов и поборов разбойников. Староста ищет защитников для путников "
        "и караванов.",
    )
    cat["lore_chernoles"] = LoreEntry(
        name="Чернолесье", category="location",
        description="Чернолесье — густой древний лес к северу от трактов. Полнится волками, "
        "гоблинскими стоянками и слухами о некроманте, поднимающем мёртвых среди старых курганов.",
    )
    cat["lore_guild"] = LoreEntry(
        name="Гильдия Серебряного Тракта", category="faction",
        description="Купеческая гильдия, контролирующая торговые пути между городами. Нанимает "
        "отряды для охраны караванов, щедро платит за расчистку дорог от разбойников и тварей, но "
        "не прощает срыва контрактов.",
    )
    cat["lore_curse"] = LoreEntry(
        name="Проклятие Старых Курганов", category="history",
        description="Древнее поверье: курганы павших королей хранят сокровища, но потревоженные "
        "мертвецы встают на защиту. Некроманты Чернолесья, по слухам, научились пробуждать их и "
        "вести за собой.",
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
