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
        name="Кинжал", description="Лёгкий клинок — самое распространённое оружие в гетто Нижних Граней и подворотнях Аники. Незаметен под плащом, смертоносен вблизи.",
        damage_dice="1d6", price=5,
    )
    cat["short_sword"] = Weapon(
        name="Короткий меч", description="Штатный клинок стражников среднего ранга и армейских пехотинцев. Надёжен, но немного сковывает реакцию.",
        damage_dice="1d8", str_requirement=5, price=10,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -1, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Короткий меч: DEX -1")],
    )
    cat["greataxe"] = Weapon(
        name="Двуручный топор", description="Топор орков-рабочих, переделанный в боевое оружие. Требует богатырской силы — Гро с ним управляются лучше, чем люди.",
        damage_dice="2d8", str_requirement=8, price=15,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -3, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Двуручный топор: DEX -3")],
    )
    cat["staff"] = Weapon(
        name="Посох", description="Деревянный шест. В центральных Гранях — оружие неудачника. В руках шамана с севера или мага из Тенелесья — орудие концентрации силы.",
        damage_dice="1d4", price=5,
        effects=[_stat_eff(EffectTarget.WISDOM, 2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Посох: WIS +2")],
    )
    cat["bow"] = Weapon(
        name="Лук", description="Традиционное оружие следопытов Тенелесья и охотников Вьюжных Пределов. В промышленной Грани уступил место арбалету, но в лесу ему нет равных.",
        damage_dice="1d8", dex_requirement=7, price=8, is_ranged=True,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Лук: DEX +2")],
    )
    cat["crossbow"] = Weapon(
        name="Арбалет", description="Стандартное оружие городской стражи Аники и гарнизонов Пепельного Дозора. Мощный, надёжный, не требует годов обучения — именно то, что нужно рядовому солдату.",
        damage_dice="1d8", str_requirement=7, price=10, is_ranged=True,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Арбалет: DEX +2")],
    )
    cat["homing_bow"] = Weapon(
        name="Лук с самонаводящимися стрелами", damage_dice="1d8", dex_requirement=7,
        price=12, is_ranged=True, is_unique=True,
        description="Артефакт из глубин Тенелесья: зачарованные стрелы сами находят цель. Игнорируют Бастион и бьют любую видимую цель. Лесные маги продают такие редко и неохотно.",
        effects=[
            _stat_eff(EffectTarget.DEXTERITY, 2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON,
                      "Лук с самонаведением: DEX +2"),
            _attr_eff(EffectTarget.IGNORE_BASTION, 0, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON,
                      "Самонаводящиеся стрелы: игнорируют Бастион"),
        ],
    )
    cat["spear"] = Weapon(
        name="Копьё", description="Длинное древковое оружие — хороший баланс досягаемости и урона. Предпочитают северные кланы и ополченцы из резерваций Гро.",
        damage_dice="1d6", str_requirement=4, price=6,
        effects=[_stat_eff(EffectTarget.STRENGTH, 2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Копьё: STR +2")],
    )
    cat["club"] = Weapon(
        name="Дубина", description="Любимое оружие орков-рабочих в гетто. Дёшево, просто, сердито — и всегда под рукой в виде рукоятки от шахтного инструмента.",
        damage_dice="1d6", price=3,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -1, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Дубина: DEX -1")],
    )
    cat["battle_axe"] = Weapon(
        name="Боевой топор", description="Переделка шахтёрского инструмента в боевое оружие — распространена среди бандитов и бойцов подполья. Наносит серьёзные повреждения.",
        damage_dice="1d10", str_requirement=7, price=7,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -2, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Боевой топор: DEX -2")],
    )
    cat["halberd"] = Weapon(
        name="Бердыш", description="Тяжёлое церемониальное оружие элитных частей стражи Аники — им вооружены ворота дворца и штаб-квартиры Совета. Разрушительный урон ценой чудовищной неповоротливости.",
        damage_dice="2d10", str_requirement=9, price=14,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -4, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Бердыш: DEX -4")],
    )
    cat["steam_pistol"] = Weapon(
        name="Стим-пистолет", description="Контрабандное огнестрельное оружие на паровых зарядах. Стреляет разрывными капсулами с оглушительным треском. Незаконно на всей территории империи — на чёрном рынке Аники стоит как недельный заработок заводского мастера. Засветиться с ним — прямая дорога в тюрьму.",
        damage_dice="2d6", str_requirement=5, price=25, is_ranged=True, is_unique=True,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 1, SourceType.WEAPON, ActivationSource.EQUIPPED_WEAPON, "Стим-пистолет: DEX +1")],
    )

    # ───────── броня (§14) ─────────
    cat["leather"] = Armor(
        name="Кожаная броня", description="Дублёная кожа — стандартная защита бандитов, торговцев и путников на дорогах империи. Не стесняет движений, но от серьёзного удара не спасёт.",
        phys_def_bonus=1, price=8,
    )
    cat["chainmail"] = Armor(
        name="Кольчуга", description="Армейская кольчуга — стандарт пехоты Грохании. Сотни стальных колец защищают от клинков, но сковывают ловкость.",
        phys_def_bonus=2, str_requirement=5, price=12,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -1, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Кольчуга: DEX -1")],
    )
    cat["plate"] = Armor(
        name="Латный доспех", description="Парадная броня рыцарей и офицеров Грохании. Максимальная защита ценой резкого снижения манёвренности — в промышленных коридорах просто неудобен.",
        phys_def_bonus=3, str_requirement=7, price=15,
        effects=[_stat_eff(EffectTarget.DEXTERITY, -3, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Латный доспех: DEX -3")],
    )
    cat["mage_robes"] = Armor(
        name="Одеяния мага", description="Зачарованные мантии северных или лесных магов. В центральных Гранях их ношение вызывает подозрение — магия здесь считается «варварством». Концентрируют магическую силу носителя.",
        phys_def_bonus=0, price=8,
        effects=[_stat_eff(EffectTarget.WISDOM, 2, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Одеяния мага: WIS +2")],
    )
    cat["enchanted_robes"] = Armor(
        name="Зачарованные одеяния", description="Одеяния высшего мага Тенелесья — тонкая ткань, насыщенная лесной магией из первородных источников. В Грани их не найдёшь в открытой продаже.",
        phys_def_bonus=0, price=15,
        effects=[_stat_eff(EffectTarget.WISDOM, 3, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Зачарованные одеяния: WIS +3")],
    )
    cat["berserker_armor"] = Armor(
        name="Доспех берсерка", description="Боевая броня кланов Вьюжных Пределов. Северяне верят, что металл, закалённый в снегу и ярости, даёт носителю силу — и они правы.",
        phys_def_bonus=2, str_requirement=6, price=15,
        effects=[
            _stat_eff(EffectTarget.STRENGTH, 3, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Доспех берсерка: STR +3"),
            _stat_eff(EffectTarget.DEXTERITY, -3, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Доспех берсерка: DEX -3"),
        ],
    )
    cat["scout_armor"] = Armor(
        name="Лёгкий доспех разведчика", description="Доспех следопытов Тенелесья: лёгкий, не стесняет движений, сшит из кожи с вставками из магического дерева. Идеален для лесной засады и быстрого отхода.",
        phys_def_bonus=1, price=12,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 1, SourceType.ARMOR, ActivationSource.EQUIPPED_ARMOR, "Лёгкий доспех разведчика: DEX +1")],
    )
    cat["miner_suit"] = Armor(
        name="Шахтёрский защитный костюм", description="Усиленный рабочий костюм из толстой кожи с металлическими накладками. Стандартная экипировка надзирателей на рудниках Граней. Защищает от взрывов, обвалов и удара заводского инструмента.",
        phys_def_bonus=2, str_requirement=4, price=10,
    )

    # ───────── зелья (§14) ─────────
    cat["small_heal"] = Item(
        name="Малое зелье лечения", description="Маленький пузырёк зелья — быстро затягивает незначительные порезы и ссадины.",
        heal_dice="1d4", price=4, is_consumable=True,
    )
    cat["heal"] = Item(
        name="Зелье лечения", description="Добротное зелье — возвращает силы после серьёзных боевых ранений.",
        heal_dice="2d4", price=6, is_consumable=True,
    )
    cat["big_heal"] = Item(
        name="Большое зелье лечения", description="Мощный эликсир восстановления, способный поднять воина даже с порога смерти.",
        heal_dice="3d4", price=10, is_consumable=True,
    )

    # ───────── магические предметы (§14) ─────────
    cat["luck_talisman"] = Item(
        name="Талисман удачи", description="Зачарованный амулет с клевером — судьба благосклоннее к носителю во всех бросках.",
        price=10,
        effects=[_attr_eff(EffectTarget.ALL_D20_ROLLS, 2, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Талисман удачи: +2 ко всем d20")],
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
        price=25, is_unique=True,
        effects=[_stat_eff(EffectTarget.DEXTERITY, 4, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Сапоги тени: DEX +4")],
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
        name="Фокус мага", description="Хрустальный шар — концентрирует магию, усиливает мудрость чародея.",
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
    cat["ash_mask"] = Item(
        name="Маска дозорного", description="Кожаная маска с угольными фильтрами и огромными стеклянными очками — стандартное снаряжение Пепельного Дозора. Незаменима в Пустыне Смерти: защищает от пепла, токсичного воздуха и слабых кислотных осадков Граней. В гарнизоне Пеплограда без неё из казармы не выходят.",
        price=5,
        effects=[_attr_eff(EffectTarget.PHYS_DEFENSE, 1, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Маска дозорного: +1 физ.защ.")],
    )
    cat["wanderer_cloak"] = Item(
        name="Плащ странника", description="Уникальный плащ воинов Тенелесья — пропитан лесной смолой и зачарован против обнаружения. Скрывает силуэт и немного рассеивает удары.",
        price=18, is_unique=True,
        effects=[
            _stat_eff(EffectTarget.DEXTERITY, 1, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Плащ странника: DEX +1"),
            _attr_eff(EffectTarget.PHYS_DEFENSE, 1, SourceType.ITEM, ActivationSource.IN_INVENTORY, "Плащ странника: +1 физ.защ."),
        ],
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
        name="Том «Магические стрелы»", description="Том залпового заклинания. Выпускает 4 самонаводящиеся стрелы в цель.",
        spell_name="Магические стрелы",
        damage_dice="4d4", difficulty=10, attack_stat="wisdom", price=7,
    )
    cat["tome_fireball"] = SpellBook(
        name="Том «Огненный шар»",
        description="Том огненного взрыва. Основная цель — полный урон, все прочие враги получают AoE-взрыв.",
        spell_name="Огненный шар", damage_dice="2d6", aoe_damage_dice="1d6",
        difficulty=12, attack_stat="wisdom", price=20,
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
    cat["scroll_lightning"] = Scroll(
        name="Свиток «Молния»",
        description="Одноразовый свиток: мощный разряд молнии бьёт одну цель с огромной силой.",
        spell_name="Молния", damage_dice="1d12", difficulty=10, attack_stat="wisdom", price=10,
    )
    cat["scroll_ray"] = Scroll(
        name="Свиток «Магический луч»",
        description="Одноразовый свиток: концентрированный луч силы бьёт одну цель.",
        spell_name="Магический луч", damage_dice="1d10", difficulty=8, attack_stat="wisdom", price=5,
    )
    cat["scroll_arrows"] = Scroll(
        name="Свиток «Магические стрелы»",
        description="Одноразовый свиток: залп из четырёх самонаводящихся стрел поражает цель.",
        spell_name="Магические стрелы", damage_dice="4d4", difficulty=10, attack_stat="wisdom", price=7,
    )
    cat["scroll_frost_sphere"] = Scroll(
        name="Свиток «Сфера холода»",
        description="Одноразовый свиток: тяжёлый шар льда замораживает и ранит одну цель.",
        spell_name="Сфера холода", damage_dice="1d10", difficulty=9, attack_stat="wisdom", price=7,
    )

    # ───────── навыки (механика тома/лютни, но вне инвентаря, не продаются) ─────────
    cat["skill_magic_arrows"] = Skill(
        name="Навык «Магические стрелы»",
        description="Выучен из тома. Постоянно: персонаж кастует залп магических стрел.",
        is_passive=False, price=12,
        spell_name="Магические стрелы", damage_dice="4d4", difficulty=10, attack_stat="wisdom",
    )
    cat["tome_arrows"].teaches_skill = cat["skill_magic_arrows"]

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
    cat["inspiring_lute"].grants_skill = cat["skill_battle_song"]
    cat["war_drum"].grants_skill = cat["skill_war_cry"]

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
    cat["improdor_defender"].grants_skill = cat["skill_bastion"]

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

    cat["skill_magic_ray"] = Skill(
        name="Навык «Магический луч»",
        description="Выучен из тома. Постоянно: персонаж кастует концентрированный луч силы.",
        is_passive=False, price=10,
        spell_name="Магический луч", damage_dice="1d10", difficulty=8, attack_stat="wisdom",
    )
    cat["tome_ray"].teaches_skill = cat["skill_magic_ray"]

    cat["skill_lightning"] = Skill(
        name="Навык «Молния»",
        description="Выучен из тома. Постоянно: персонаж наносит мощнейший молниеносный удар.",
        is_passive=False, price=18,
        spell_name="Молния", damage_dice="1d12", difficulty=10, attack_stat="wisdom",
    )
    cat["tome_lightning"].teaches_skill = cat["skill_lightning"]

    cat["skill_frost_sphere"] = Skill(
        name="Навык «Сфера холода»",
        description="Выучен из тома. Постоянно: персонаж кастует тяжёлый шар льда.",
        is_passive=False, price=15,
        spell_name="Сфера холода", damage_dice="1d10", difficulty=9, attack_stat="wisdom",
    )
    cat["tome_frost_sphere"].teaches_skill = cat["skill_frost_sphere"]

    # ───────── игровые персонажи (§15) ─────────
    cat["enzo"] = Character(
        name="Энцо",
        description="Грохонец (полукровка человека и орка) из Нижних Граней Аники. Вырос в гетто рядом с гоблинской мафией — сначала бегал курьером, потом научился вскрывать замки и чужие кошельки. Ни революционерам, ни Культу Бурь не верит: слишком насмотрелся на обе стороны. Работает на того, кто платит, — но есть вещи, которые не продаст даже за золото. Архетип: Плут / Разбойник.",
        is_player=True,
        base_strength=3, base_dexterity=12, base_wisdom=5, base_charisma=8, money=0,
        equipped_weapon=cat["dagger"], equipped_armor=cat["leather"],
        inventory=[cat["small_heal"], cat["luck_talisman"], cat["inspiring_lute"]],
    )
    cat["andryusha"] = Character(
        name="Андрюша",
        description="Человек, бывший стражник третьего ранга в гарнизоне Аники. Вырос в рабочем квартале Средних Граней, записался в стражу ради стабильного жалования. Ушёл, когда понял, что Культ Бурь внутри — не слухи, а приказы командиров. Теперь наёмник без политических предпочтений: к оркам и грохонцам относится спокойнее большинства, верит в честную работу и хорошую сталь. Архетип: Воин.",
        is_player=True,
        base_strength=12, base_dexterity=5, base_wisdom=3, base_charisma=5, money=1,
        inventory=[cat["improdor_defender"]],
        equipped_weapon=cat["short_sword"], equipped_armor=cat["chainmail"],
    )
    cat["salli"] = Character(
        name="Салли",
        description="Полуэльф из приграничья Тенелесья. Мать — эльфийка из Сильванара, отец — заезжий торговец, которого она никогда не знала. В лесу её принимали как чужую, в городе смотрели на неё как на диковинку. Стала следопытом: в Тенелесье нужны навыки, а не происхождение. Знает лесные тропы лучше большинства чистокровных эльфов, но в имперских городах чувствует себя не в своей тарелке. Насторожённо относится к промышленной экспансии Граней в лес. Архетип: Следопыт / Лучник.",
        is_player=True,
        base_strength=5, base_dexterity=10, base_wisdom=7, base_charisma=3, money=2,
        equipped_weapon=cat["homing_bow"], equipped_armor=cat["leather"],
        inventory=[cat["small_heal"]],
    )
    cat["arseldor"] = Character(
        name="Арсельдор",
        description="Человек из Средних Граней, самоучка-маг. Магические способности открылись после случайного контакта с артефактом из Пустыни Смерти — предположительно технологией Анхари, которую он принял за волшебство. В центральных Гранях магия официально считается «архаизмом» и «варварством», поэтому практикует втайне. Одержим историей Анхари и убеждён, что их утраченные технологии и магия Гро — одно и то же явление. Собирает запрещённые книги. Архетип: Маг.",
        is_player=True,
        base_strength=3, base_dexterity=3, base_wisdom=14, base_charisma=5, money=0,
        equipped_weapon=cat["staff"], equipped_armor=cat["mage_robes"],
        inventory=[cat["vitality_amulet"]],
        skills=[cat["skill_magic_arrows"]],
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
        name="Городской стражник", description="Рядовой стражи Аники — хорошо обучен, действует по уставу. Большинство — честные служаки. Среди них, однако, немало тайных членов Культа Бурь: распознать таких можно по серебряному значку под воротником.",
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
        name="Орк", description="Рабочий класс Грохании — кто-то после смены на шахте, кто-то из безработных гетто. Физически мощный, умеет злиться. Поодиночке не агрессивен, но легко поддаётся агитации через простые лозунги. С оружием в руках — серьёзная угроза.",
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
        name="Огр", description="Де-факто раб на тяжелейших работах Грани — тягловая сила шахт и строек. Не понимает лозунгов и политики. Его держат в повиновении примитивной магией или обещанием еды. Опасен, если разозлить или обмануть.",
        is_sentient=True,
        hp=25, dexterity=3, phys_defense=12, mag_defense=3, mental_defense=5,
        phys_damage_dice="1d12", strength=12, charisma=1, wisdom=1,
    )
    cat["troll"] = Creature(
        name="Тролль", description="Рабочий в шахтах и на строительстве — физически мощный, с толстой кожей. Не понимает политики, но реагирует на несправедливость инстинктивно: может взорваться без предупреждения. Говорят, мелкие раны затягиваются у него прямо в бою.",
        is_sentient=True,
        hp=20, dexterity=4, phys_defense=11, mag_defense=4, mental_defense=6,
        phys_damage_dice="1d10", strength=10, charisma=1, wisdom=2,
    )
    cat["goblin"] = Creature(
        name="Гоблин", description="Маленький зелёный обжитель гетто. Слаб телом, но хитёр умом. Работает курьером, стукачом, мелким контрабандистом — другого выхода в гетто нет. Организован в гоблинскую мафию: самый сплочённый народ среди Гро, выживание сделало их такими.",
        is_sentient=True,
        hp=3, dexterity=8, phys_defense=6, mag_defense=2, mental_defense=5,
        phys_damage_dice="1d3", strength=1, charisma=3, wisdom=4,
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
    cat["pirate"] = Creature(
        name="Пират", description="Морской разбойник с саблей — быстр, безжалостен и привычен к ближней схватке.",
        is_sentient=True,
        hp=12, dexterity=7, phys_defense=9, mag_defense=2, mental_defense=6,
        phys_damage_dice="1d8", strength=5, charisma=3, wisdom=3,
    )
    cat["cultist"] = Creature(
        name="Адепт Культа Бурь", description="Рядовой член тайного Культа Бурь — стражник или солдат, потерявший кого-то от рук революционеров. Искренне верит в «чистоту крови» и «порядок». Серебряная молния под воротником — тайный знак. Слаб телом, но опасен фанатизмом и связями внутри стражи.",
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
        name="Шаман", description="Духовный лидер кланов Вьюжных Пределов. Общается с духами предков, льда и ветра. В центральных Гранях их считают «дикарями», но в своих землях они — настоящая власть. Ослабляет врагов проклятием духов.",
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
        name="Каменный голем", description="Магически оживлённый страж из камня — скорее всего артефакт времён Великого Синтеза или охрана древнего хранилища Анхари. Медленен, но практически неуязвим физически. На чёрном рынке за картой к такому хранилищу дают целое состояние.",
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

    # ── NPC ──
    cat["revolutionary"] = Creature(
        name="Революционер", description="Боевик революционного подполья — орк или грохонец с личным счётом к власти. Обучен азам тактики подпольной борьбы: засады, саботаж, баррикады. Опасен фанатизмом и готовностью умереть за лозунг «Гро — едины!».",
        is_sentient=True,
        hp=12, dexterity=6, phys_defense=9, mag_defense=2, mental_defense=9,
        phys_damage_dice="1d8", strength=6, charisma=4, wisdom=3,
    )
    cat["ash_zombie"] = Creature(
        name="Пепельный зомби", description="Нежить Пустыни Смерти — безликая гуманоидная фигура из пепла и костей. Порождена душами погибших Анхари. Из пустых глазниц сыплется пепел. Медленная, но неостановимая. Один — не проблема; толпа из сотен — катастрофа.",
        is_sentient=False,
        hp=10, dexterity=2, phys_defense=7, mag_defense=1, mental_defense=20,
        phys_damage_dice="1d6", strength=5, charisma=1, wisdom=1,
    )
    cat["ash_ghoul"] = Creature(
        name="Пепельный упырь", description="Нежить Пустыни Смерти — тощее, непропорционально высокое существо с длинными руками и ногами. Кожа из спечённого пепла и костей. Быстрое, охотится стаями, взбирается по отвесным стенам и бортам наземных кораблей.",
        is_sentient=False,
        hp=8, dexterity=9, phys_defense=8, mag_defense=2, mental_defense=20,
        phys_damage_dice="1d8", strength=4, charisma=1, wisdom=2,
    )
    cat["npc_innkeeper"] = Creature(
        name="Трактирщик", description="Хозяин таверны в Нижних или Средних Гранях: наливает мутное эль, сдаёт комнаты и охотно делится новостями и сплетнями за пару монет. Одним ухом слышит всё — одним глазом видит, чего лучше не замечать.",
        is_sentient=True, hp=8, dexterity=3, phys_defense=9, mag_defense=2, mental_defense=6,
        phys_damage_dice="1d4", strength=4, charisma=7, wisdom=5,
    )

    # ───────── лор-записи о мире (RAG-база фактов для ИИ-ГМа) ─────────
    cat["lore_h_001"] = LoreEntry(
        lore_id="H-001",
        name="История / Анхари",
        category="ИСТОРИЯ",
        description="Народ Анхари (самоназвание) построил великую цивилизацию Анхара (Златозёмье): поэзия, музыка, архитектура, зачатки паровых технологий. Это было развитое общество, а не варвары. Народ Анхара не знал магии и не умел ее применять, поэтому в достижениях опирался на технологии, используя магию и сточники магии как топливо для своих машин",
        when_to_apply="Упоминание прошлого, артефакты, барды, древние тексты",
        notes="Анхари ≠ современные «люди». Это предки. Современные люди зовут себя просто «людьми»",
    )
    cat["lore_h_002"] = LoreEntry(
        lore_id="H-002",
        name="История / Грех Анхари",
        category="ИСТОРИЯ",
        description="Анхари истощили магические источники, выжгли леса, отравили реки ради ресурсов и топлива для своих механических изобритений. Они верили, что земля бесконечна и существует для их блага. Именно это привело к Великому Катаклизму.",
        when_to_apply="Экологические темы, параллели с нынешней Гроханией, нарративы о жадности",
        notes="Это не просто «они были плохими» — это история повторяющейся ошибки. Грохания делает то же самое сейчас",
    )
    cat["lore_h_003"] = LoreEntry(
        lore_id="H-003",
        name="История / Катаклизм",
        category="ИСТОРИЯ",
        description="Великий Катаклизм: магические источники иссякли, почвы отравились, реки высохли, начались пожары и землетрясения. Сама земная кора треснула и начала извергаться лава. Цивилизация Анхари сгорела за несколько десятилетий. Анхара превратилась в Пепельную Пустошь.",
        when_to_apply="Пустыня Смерти, артефакты, философские разговоры о цикличности",
        notes="Катаклизм — не внешняя атака. Это самоуничтожение через жадность",
    )
    cat["lore_h_004"] = LoreEntry(
        lore_id="H-004",
        name="История / Наземные корабли",
        category="ИСТОРИЯ",
        description="Выжившие Анхари построили наземные корабли-города — огромные крепости на гусеницах или паровых ногах. Они стали новым домом на столетия. Анхари из развитой цивилизации превратились в качевников, занимающимся мородерством своих же покинутых и разрушенных поселений. Каждый корабль стал отдельным городом-государством с вождём-ханом.",
        when_to_apply="Пустыня Смерти, артефакты Анхари, квесты-экспедиции, разговоры о прошлом",
        notes="Заброшенные корабли до сих пор стоят в Пустыне — источник артефактов, записей, опасности",
    )
    cat["lore_h_005"] = LoreEntry(
        lore_id="H-005",
        name="История / Вечный Ужас",
        category="ИСТОРИЯ",
        description="Кочуя по Пустоши, Кочевники Ханы, бывшие Анхари, нашли нечто в её глубинах — Вечный Ужас. Летописи об этом уничтожены по приказу власти. Именно встреча с Вечным Ужасом заставила разрозненные племена объединиться вновь, чтобы найти выход из Пустыни Смерти и пересечь Пепельный Рубеж.",
        when_to_apply="Культ Бурь, легенды, квесты в Пустыне, расспросы о прошлом",
        notes="Природа Вечного Ужаса — намеренная загадка. Нарратор не должен давать точный ответ",
    )
    cat["lore_h_006"] = LoreEntry(
        lore_id="H-006",
        name="История / Великий Исход",
        category="ИСТОРИЯ",
        description="720 лет назад объединённый Великий Караван Анхари пересёк Пепельный Рубеж. Многие корабли и люди погибли, но выжившие вышли к плодородным землям Гро. Именно это объединение перед лицом смерти стало мифологической основой Культа Бурь.",
        when_to_apply="Основание империи, Культ Бурь, барды, легенды",
        notes="«Ханы» — это прозвище, которое Гро дали пришедшим (от «хан» — предводитель или искажённое «Анхари»). Сами себя они так не называли",
    )
    cat["lore_h_007"] = LoreEntry(
        lore_id="H-007",
        name="История / Земли Гро и первые годы",
        category="ИСТОРИЯ",
        description="Первые десятилетия после прихода Анхари были кровавыми. Анхари поняли, что не удержат территорию в одиночестве — Гро знают местность. Гро не могли противостоять технологиям Анхари. Начался Великий Синтез.",
        when_to_apply="Разговоры об истории, квесты по архивам, NPC-историки",
        notes="Официальная версия: добровольное сотрудничество равных. Реальность: неравный союз силы",
    )
    cat["lore_h_008"] = LoreEntry(
        lore_id="H-008",
        name="История / Великий Синтез",
        category="ИСТОРИЯ",
        description="Великий Синтез (~720 лет назад): Анхари принесли технологии, письменность, культуру. Гро дали рабочую силу, знание недр, физическую мощь. Так родилась Грохания. Началось кровосмешение.",
        when_to_apply="Основание империи, полукровки, исторические споры",
        notes="Синтез ≠ равноправие. Анхари занимали господствующее положение с самого начала",
    )
    cat["lore_h_009"] = LoreEntry(
        lore_id="H-009",
        name="История / Закон о Забвении",
        category="ИСТОРИЯ",
        description="В 517 году (≈200 лет после основания) Закон о Забвении запретил слова «Ханы», «Гро», «Анхари». Все граждане стали «Грохонцами». Библиотеки прочищались, хроники переписывались, надписи на зданиях менялись.",
        when_to_apply="Документы, суды, упоминание рас, запрещённые слова",
        notes="Закон задумывался как объединяющий. Результат: загнал расовый вопрос в подполье и стал инструментом репрессий",
    )
    cat["lore_h_010"] = LoreEntry(
        lore_id="H-010",
        name="История / До сегрегации",
        category="ИСТОРИЯ",
        description="Жёсткая сегрегация, гетто и эксплуатация Гро — явление ПОСЛЕДНИХ 50-80 лет. Старейшие жители помнят, когда орки и люди жили гораздо более интегрированно. Большое число грохонцев (полукровок) — прямое свидетельство этого.",
        when_to_apply="Разговоры со старыми NPC, исторические архивы, объяснение наличия полукровок",
        notes="НЕ говорить «всегда так было». Это критически важный нюанс мира",
    )
    cat["lore_h_011"] = LoreEntry(
        lore_id="H-011",
        name="История / Захват власти",
        category="ИСТОРИЯ",
        description="Около 50-80 лет назад группа богатейших олигархов захватила реальное управление через Совет Анхари. Они начали целенаправленно усиливать сегрегацию, чтобы стравить народы и скрыть собственное обогащение за счёт эксплуатации.",
        when_to_apply="Политические квесты, расследования, разговоры о «почему стало хуже»",
        notes="Совет Анхари не «изобрёл» расизм — он его инструментализировал и усилил",
    )
    cat["lore_r_001"] = LoreEntry(
        lore_id="R-001",
        name="Расы / Люди — большинство",
        category="РАСА",
        description="Большинство людей — обычные труженики: крестьяне, ремесленники, торговцы, солдаты. Они не «фашисты» по умолчанию. В быту зовут себя «люди». В документах — «грохонцы». Многие из них жили в нормальных отношениях с орками ещё полвека назад.",
        when_to_apply="Любой NPC человеческой расы в бытовой ситуации",
        notes="Националисты и Культ Бурь — это МЕНЬШИНСТВО среди людей. Не обобщать",
    )
    cat["lore_r_002"] = LoreEntry(
        lore_id="R-002",
        name="Расы / Люди — националисты",
        category="РАСА",
        description="Националисты — интеллигентное меньшинство: учёные, писатели, офицеры. Верят в «чистоту крови» и величие Анхари. Пишут памфлеты, читают лекции в университетах. Многие наивно не знают, что их финансирует Совет Анхари.",
        when_to_apply="Университеты, офицерские собрания, памфлеты, политические дебаты",
        notes="Националисты ≠ Культ Бурь. Националисты — слова и идеи. Культ Бурь — организованное насилие",
    )
    cat["lore_r_003"] = LoreEntry(
        lore_id="R-003",
        name="Расы / Грохонцы — большинство",
        category="РАСА",
        description="Большинство грохонцев (полукровок людей и орков) — обычные рабочие, ремесленники, инженеры, торговцы, мелкие чиновники. Они хотят жить спокойно. Боятся революции и хаоса больше, чем несправедливости. Внешне: зеленоватая кожа, клыки, человеческие черты.",
        when_to_apply="NPC-торговцы, инженеры, надзиратели, чиновники",
        notes="НЕ делать всех грохонцев революционерами. Большинство — тихое болото",
    )
    cat["lore_r_004"] = LoreEntry(
        lore_id="R-004",
        name="Расы / Грохонцы — идеологи революции",
        category="РАСА",
        description="Полукровки среди грохонцев — главные идеологи революционного движения. Причина: они обладают интеллектом людей (могут писать манифесты, планировать) + выносливостью орков + личной обидой от обеих сторон. Они не принятые ни теми, ни другими.",
        when_to_apply="Подпольные кружки, революционные листовки, лидеры восстания",
        notes="Идеолог ≠ боевик. Грохонцы дают план, орки — физическую силу",
    )
    cat["lore_r_005"] = LoreEntry(
        lore_id="R-005",
        name="Расы / Орки — пролетариат",
        category="РАСА",
        description="Орки — рабочий класс. Умнее огров и троллей, способны к обучению, управляют паровыми молотами, работают на сложных производствах. Большинство — обычные работяги: пьют эль в таверне, растят детей, ссорятся с соседями.",
        when_to_apply="Заводы, шахты, гетто, рынки, таверны в рабочих кварталах",
        notes="Орки ≠ все революционеры. Они чувствуют несправедливость, но инициатива исходит от грохонцев-идеологов",
    )
    cat["lore_r_006"] = LoreEntry(
        lore_id="R-006",
        name="Расы / Орки — боевая сила революции",
        category="РАСА",
        description="Орки — мышцы революции. Они легко поддаются агитации через простые лозунги («Ханы отняли наши земли!»). Физически самые сильные и стойкие бойцы на баррикадах. Помнят историю через устные эпосы о свободе.",
        when_to_apply="Агитация, баррикады, забастовки, столкновения с Культом Бурь",
        notes="Орки не понимают сложных политических теорий — их агитируют через эмоции и конкретные образы",
    )
    cat["lore_r_007"] = LoreEntry(
        lore_id="R-007",
        name="Расы / Огры",
        category="РАСА",
        description="Огры — наименее интеллектуальные из Гро. Используются как тягловая сила и де-факто рабы. Работают за еду и кров. Не понимают лозунгов и политики. Их держат в повиновении примитивной магией, стимуляторами или просто обманом («хорошо работаешь — получишь много мяса»).",
        when_to_apply="Самые тяжёлые работы, шахты, строительство",
        notes="Огр — не злодей, не союзник, не враг. Он жертва, которая не осознаёт своего положения",
    )
    cat["lore_r_008"] = LoreEntry(
        lore_id="R-008",
        name="Расы / Тролли",
        category="РАСА",
        description="Тролли — физически очень сильны, интеллект между орками и ограми. Работают в шахтах, на строительстве. Примитивные ритуалы, поклонение силе. Не понимают политики, но реагируют на насилие и несправедливость инстинктивно.",
        when_to_apply="Шахты, строительство, физическая охрана",
        notes="Тролль может взорваться от несправедливости, не понимая причины. Это опасная непредсказуемость",
    )
    cat["lore_r_009"] = LoreEntry(
        lore_id="R-009",
        name="Расы / Северяне",
        category="РАСА",
        description="Северяне (Вьюжные Пределы) — люди, но на 1-2 головы крупнее и мощнее анхари. Светлая кожа, как правило светлые волосы, серые/голубые глаза. Кланы, вожди, шаманы. Презирают «слабых южан, продавшихся машинам».",
        when_to_apply="Квесты на севере, встреча с северянами, торговля с Ледоградом",
        notes="Северяне ≠ дикари. У них богатая устная культура и шаманизм, просто нетехнологическая цивилизация",
    )
    cat["lore_r_010"] = LoreEntry(
        lore_id="R-010",
        name="Расы / Эльфы",
        category="РАСА",
        description="Эльфы Тенелесья — высокие, стройные, долгоживущие. Маги, лучники, следопыты. Живут веками. Не понимают, почему люди так спешат. Люди завидуют их долголетию. Помнят Великую Вырубку и не доверяют империи.",
        when_to_apply="Тенелесье, лесные квесты, магические предметы",
        notes="Эльфы ≠ союзники по умолчанию. Их напряжённость с империей реальна",
    )
    cat["lore_r_011"] = LoreEntry(
        lore_id="R-011",
        name="Расы / Друиды",
        category="РАСА",
        description="Друиды — люди или полуэльфы, посвятившие себя служению лесу. Шаманы природы. Управляют доступом к магической древесине. Именно они вели переговоры с империей 300 лет назад. Некоторые молодые друиды симпатизируют революционерам.",
        when_to_apply="Тенелесье, природная магия, экологические конфликты",
        notes="Друид ≠ беспомощный миролюбец. Они могут быть опасными защитниками леса",
    )
    cat["lore_r_012"] = LoreEntry(
        lore_id="R-012",
        name="Расы / Нимфы и духи леса",
        category="РАСА",
        description="Нимфы — духи леса, воды, деревьев в Тенелесье. Редко появляются перед людьми. Лесные духи — невидимые существа, защищающие лес. Реагируют на угрозу экосистеме.",
        when_to_apply="Глубокий лес, магические источники, экологические кризисы",
        notes="Нимфы и духи — не NPC для торговли. Их появление — событие",
    )
    cat["lore_r_013"] = LoreEntry(
        lore_id="R-013",
        name="Расы / Гоблины",
        category="РАСА",
        description="Гоблины - маленькие зеленые существа, представляющие еще одну расу народа \"Гро\" слабого телосложения. Лучше соображают чем орки, но ввиду отсутствия физичкой силы абсолютно бесполны для работы в шахтах и заводах. В условиях жизни в гетто им ничего не остается кроме того, чтобы заниматься криминалом, попрошайничеством и мелкими поручениями, вроде доставок.",
        when_to_apply="Криминал, гетто, рынки, таверны в рабочих кварталах",
        notes="Гоблины по факту самый сплоченный народ среди всех Гро, организовали свою Мафию, посокльку это стало средством их выживания",
    )
    cat["lore_p_001"] = LoreEntry(
        lore_id="P-001",
        name="Политика / Монарх",
        category="ПЕРСОНАЖ",
        description="СлабыйИмператор — марионетка. Некомпетентен. Власть ему не интересна. Его больше интересуют балы и почести нежели реальные дела. Искренне верит, что правит сам. Поддерживает миф о «дружбе народов», чтобы не допустить гражданской войны. Его решения ведут к обогащению одних и тех же семей — но он этого не замечает.",
        when_to_apply="Тронный зал, государственные решения, придворные интриги, герольды",
        notes="Монарх — трагическая, а не злодейская фигура. Он не циник, он слеп",
    )
    cat["lore_p_002"] = LoreEntry(
        lore_id="P-002",
        name="Политика / Совет Анхари",
        category="ФРАКЦИЯ",
        description="Совет Анхари — 7-12 богатейших олигархических семей: владельцы фабрик, шахт, банков, торговых флотий. Официально не существуют — только слухи в тавернах. Прагматики, не идеологи: им важны власть и прибыль, не чистота крови.",
        when_to_apply="Расследование заговоров, высшие чиновники, «почему король так решил»",
        notes="Совет ≠ фашистская организация. Они используют расизм как инструмент. Сами они выше расовых предрассудков",
    )
    cat["lore_p_003"] = LoreEntry(
        lore_id="P-003",
        name="Политика / Совет Анхари — методы",
        category="ПОЛИТИКА",
        description="Методы Совета: коррупция, шантаж, подкуп чиновников, финансирование пропаганды, организация «несчастных случаев» для конкурентов. Они тайно финансируют и Культ Бурь, и некоторых революционеров — чтобы стравить народы между собой.",
        when_to_apply="Политические заказы, странные смерти аристократов, финансовые следы",
        notes="Совет финансирует ОБЕ стороны конфликта. Им выгоден хаос, который они контролируют",
    )
    cat["lore_p_004"] = LoreEntry(
        lore_id="P-004",
        name="Политика / Придворная аристократия",
        category="ФРАКЦИЯ",
        description="Двор делится на два лагеря: Ставленники Совета (проводят нужные законы, получили титулы через олигархов) и Старая аристократия (служат короне веками, видят происходящее, бессильны). Некоторые из Старой аристократии тихо сочувствуют Грохонцам.",
        when_to_apply="Придворные балы, политические союзники, неожиданная помощь",
        notes="Старая аристократия — потенциальный союзник игроков, которого не ожидаешь",
    )
    cat["lore_p_005"] = LoreEntry(
        lore_id="P-005",
        name="Политика / Культ Бурь — суть",
        category="ФРАКЦИЯ",
        description="Культ Бурь — тайная организация внутри армии и стражи. Риторика чистоты крови и расовой чистки. Символ: серебряная молния в песчаной розе (носят тайно — под воротником, на рукояти кинжала). Девиз: «Из Пыли — Сталь. Из Бури — Порядок.»",
        when_to_apply="Стражники, элитные войска, расследование фашистских выходок",
        notes="Культ ≠ открытая организация. Члены не признаются публично. Символ — тайный сигнал",
    )
    cat["lore_p_006"] = LoreEntry(
        lore_id="P-006",
        name="Политика / Культ Бурь — название",
        category="КОНТЕКСТ",
        description="Название «Культ Бурь» — отсылка к Пепельным Бурям Пустыни Смерти, которые были тюрьмой Анхари 720 лет назад. Они называют себя «Бурей», которая очистит империю. Посвящённые знают истинный смысл: вернуть Империю в состояние единства перед лицом смерти.",
        when_to_apply="Разговоры о символике Культа, его истории, вербовка",
        notes="Рядовые думают «буря = очищение». Руководство знает: «буря = реакционная утопия золотого века Анхари»",
    )
    cat["lore_p_007"] = LoreEntry(
        lore_id="P-007",
        name="Политика / Культ Бурь — высшее руководство",
        category="ФРАКЦИЯ",
        description="Высшее руководство Культа (5-7 генералов и адмиралов) — марионетки Совета Анхари. Они знают, что ими манипулируют, но считают это «необходимым злом»: «пусть олигархи богатеют, зато мы сохраняем порядок». Они циничны и прагматичны.",
        when_to_apply="Встречи с командованием Культа, расследование его финансирования",
        notes="Руководство Культа ≠ наивные фанатики. Они знают правду и мирятся с ней",
    )
    cat["lore_p_008"] = LoreEntry(
        lore_id="P-008",
        name="Политика / Культ Бурь — рядовые",
        category="ФРАКЦИЯ",
        description="Рядовые члены Культа — искренние фанатики. Каждый потерял кого-то от террора революционеров. Они видят саботаж, убийства, взрывы. Для них убийство орка или полукровки — восстановление справедливости. Они не понимают, что их используют.",
        when_to_apply="Патрульные, стражники, аресты Гро, допросы",
        notes="Рядовые члены — жертвы, ставшие палачами. Это трагедия, не злодейство в чистом виде",
    )
    cat["lore_p_009"] = LoreEntry(
        lore_id="P-009",
        name="Политика / Революционеры — суть",
        category="ФРАКЦИЯ",
        description="Революционное движение — не монолит. Идеологи: грохонцы (пишут манифесты, планируют операции, ведут агитацию). Боевики: орки (физическая сила, баррикады). Тактика: подрывы фабрик и шахт, покушения на аристократов, убийства надзирателей.",
        when_to_apply="Гетто, подпольные собрания, листовки, следы взрывов",
        notes="Большинство Гро и грохонцев — НЕ революционеры. Это активное меньшинство",
    )
    cat["lore_p_010"] = LoreEntry(
        lore_id="P-010",
        name="Политика / Революционеры — лозунги",
        category="КОНТЕКСТ",
        description="Главные лозунги революционеров: «Гро — едины!» (запрещено под страхом казни) и «Ханы отняли наши земли!» (запрещено). Использование слова «Гро» в политическом контексте — само по себе акт сопротивления.",
        when_to_apply="Подпольные встречи, листовки, граффити в гетто",
        notes="Произнести «Гро — едины!» публично = немедленный арест. Это важно для атмосферы",
    )
    cat["lore_p_011"] = LoreEntry(
        lore_id="P-011",
        name="Политика / Революционеры — террор",
        category="ПОЛИТИКА",
        description="Террористическая деятельность революционеров породила Культ Бурь. Это замкнутый цикл: Совет Анхари эксплуатирует → революционеры применяют террор → военные теряют друзей → Культ Бурь усиливается → репрессии → больше революционеров.",
        when_to_apply="Следы взрывов, атмосфера страха, новостные слухи в тавернах",
        notes="Цикл насилия выгоден Совету Анхари — он отвлекает от настоящего виновника",
    )
    cat["lore_p_012"] = LoreEntry(
        lore_id="P-012",
        name="Политика / Старая аристократия",
        category="ПЕРСОНАЖ",
        description="Представители Старой аристократии — роды, служившие короне веками. Видят коррупцию, манипуляции Совета, деградацию империи. Бессильны открыто выступить. Некоторые тайно помогают реформаторам или даже передают информацию революционерам.",
        when_to_apply="Неожиданная помощь, тайные встречи в особняках, квест на поиск союзников",
        notes="Не все аристократы — ставленники Совета. Искать трещины внутри элиты",
    )
    cat["lore_g_001"] = LoreEntry(
        lore_id="G-001",
        name="Geography / Карта империи",
        category="МЕСТО",
        description="Грохания: в центре — Грани (Промышленный Округ) со столицей Аника. На севере — Вьюжные Пределы (столица Ледоград). На западе — Тенелесье (столица Сильванар). На юге — Пепельный Дозор (столица Пеплоград). На востоке — Непроходимый Предел (горы). Гетто Гро — внутри Грани вокруг Аники.",
        when_to_apply="Ориентация в пространстве, путешествия, квесты в разных регионах",
        notes="Грань ≠ провинция. Это центральная земля, вокруг которой всё строится",
    )
    cat["lore_g_002"] = LoreEntry(
        lore_id="G-002",
        name="Geography / Аника",
        category="МЕСТО",
        description="Аника — столица Грохании. Увядающее барокко, проржавевшая бронза, паровые шпили. Дирижабли у облезлых мраморных шпилей. Богатые кварталы на возвышенностях или антигравитационных платформах над смогом. Гетто Гро — внизу в грязи. Казна пуста, но парады идут.",
        when_to_apply="Любое действие в столице, встречи с аристократией, гетто",
        notes="Аника — иллюзия величия. Название отсылает к «анике-воину» — хвастуну без силы",
    )
    cat["lore_g_003"] = LoreEntry(
        lore_id="G-003",
        name="Geography / Грани — промзона",
        category="МЕСТО",
        description="Промышленный Округ (Грани) — сердце империи. Равнины с залежами угля, железа, меди. Фабрики, заводы, шахты, мануфактуры. Смог, кислотные дожди, загрязнённые реки. Архитектура: угловатая, без плавных линий, паровые трубы и шестерни.",
        when_to_apply="Любая промышленная сцена, рабочие конфликты, загрязнение",
        notes="Грани буквально отражают социальное расслоение: верх = богатые, низ = Гро",
    )
    cat["lore_g_004"] = LoreEntry(
        lore_id="G-004",
        name="Geography / Грани — социальные слои",
        category="МЕСТО",
        description="Вертикальное расслоение Грани: Верхние Грани (аристократия, олигархи — дворцы, парки, чистый воздух) → Средние Грани (грохонцы, ремесленники, торговцы — в смоге, но с работой) → Нижние Грани (Гро — гетто, грязь, копоть, солнце только через грязные окна).",
        when_to_apply="Перемещение по городу, социальные контрасты, встречи с разными классами",
        notes="Чем ниже физически — тем ниже социально. Это буквальная метафора",
    )
    cat["lore_g_005"] = LoreEntry(
        lore_id="G-005",
        name="Geography / Гетто Гро",
        category="МЕСТО",
        description="Гетто в Грани — отдельные кварталы для Гро, огороженные стенами. Официально «для их безопасности». Реально — сегрегация. Трущобы, бараки, землянки. Перенаселение, болезни, преступность. Сильное влияние Культа Бурь в охране.",
        when_to_apply="Встречи с Гро, революционная агитация, квесты в гетто",
        notes="Гетто охраняется, но изнутри — активная политическая жизнь и подполье",
    )
    cat["lore_g_006"] = LoreEntry(
        lore_id="G-006",
        name="Geography / Вьюжные Пределы",
        category="МЕСТО",
        description="Вьюжные Пределы (Вьюга) — суровый север: тундра, тайга, ледники. Столица Ледоград — из чёрного камня. Северяне: кланы, вожди, шаманы. Полунезависимы — Великий Договор ~400 лет назад. Торгуют пушниной, древесиной, редкими минералами.",
        when_to_apply="Квесты на севере, торговля, шаманизм, холодная атмосфера",
        notes="Конфликт: молодёжь уезжает в города, шаманизм умирает. Имперские промышленники хотят разрабатывать священные земли",
    )
    cat["lore_g_007"] = LoreEntry(
        lore_id="G-007",
        name="Geography / Тенелесье",
        category="МЕСТО",
        description="Тенелесье (Чаща) — густые западные леса, магические источники. Столица Сильванар — город в гигантских деревьях, мосты между кронами. Эльфы, друиды, нимфы. Полунезависимы — Договор после «Великой Вырубки» ~300 лет назад.",
        when_to_apply="Лесные квесты, магическая торговля, конфликты с имперскими лесорубами",
        notes="Лесная магия угасает из-за кислотных дождей из Грани. Экологический кризис нарастает",
    )
    cat["lore_g_008"] = LoreEntry(
        lore_id="G-008",
        name="Geography / Тенелесье — архитектура",
        category="АТМОСФЕРА",
        description="Сильванар: дома из живого дерева, мосты между кронами гигантских деревьев. Одежда: лён, шерсть, кожа, зелёные и коричневые тона. Транспорт: олени, лошади, иногда гигантские птицы. Оружие: луки, кинжалы, посохи.",
        when_to_apply="Описание Тенелесья и Сильванара, погружение в атмосферу",
        notes="Контраст с индустриальной Гранью: живое vs мёртвое железо",
    )
    cat["lore_g_009"] = LoreEntry(
        lore_id="G-009",
        name="Geography / Пепельный Дозор",
        category="МЕСТО",
        description="Пепельный Дозор (Пепел/Рубеж) — южная провинция. Столица Пеплоград из чёрного камня и пепла. 5-7 крупных крепостей, десятки малых застав вдоль границы с Пустыней Смерти. Сухо, ветрено, слабые пепельные бури.",
        when_to_apply="Южные квесты, граница с Пустыней, Культ Бурь",
        notes="Дозор охраняет от угрозы, которой 700 лет никто не видел. Это провинция абсурда и тоски",
    )
    cat["lore_g_010"] = LoreEntry(
        lore_id="G-010",
        name="Geography / Пепельный Дозор — парадокс",
        category="ПОЛИТИКА",
        description="Парадокс застав: заставы существуют 700 лет. Никто уже и не помнит ради чего они существуют. История образования была зачищина. Реальные причины их существования: 1) инерция традиций, 2) олигархи используют их для отмывания денег и финансирования Культа Бурь, 3) удобное место для ссылки неугодных",
        when_to_apply="Квесты на заставах, разговоры с дозорными, расследование финансов",
        notes="На самом деле истинная природа существование дозора - сообщить, если \"Вечный Ужас\" пересечет \"Пепельный рубеж\". Но это тайна, которую нарратор не должен сообщать",
    )
    cat["lore_g_011"] = LoreEntry(
        lore_id="G-011",
        name="Geography / Дозорные — быт",
        category="БЫТ",
        description="Быт дозорных: скука, пьянство, азартные игры, драки, рассказы слухи о \"Вечном Ужасе\" (всё более фантастические). Архитектура: крепости из чёрного камня в пепле, башни с сигнальными огнями. Плащи с капюшонами от пепла, маски, тёмные тона, очки",
        when_to_apply="Сцены на заставах, встречи с дозорными, атмосфера южных земель",
        notes="Дозорные злятся на Империю, которая присылает всё меньше денег. Потенциальное место для бунта",
    )
    cat["lore_g_012"] = LoreEntry(
        lore_id="G-012",
        name="Geography / Непроходимый Предел",
        category="МЕСТО",
        description="Непроходимый Предел (Стена, Гробы) — восточный горный хребет. Высочайшие пики, вечный снег. Проходов нет, только опасные перевалы. Никто не возвращался. Слухи: драконы, древняя цивилизация, магический источник, враждебная империя, выход Вечного Ужаса.",
        when_to_apply="Разговоры о неизведанном, высокоуровневые квесты, тайны",
        notes="Что за горами — намеренная загадка. Нарратор не должен раскрывать",
    )
    cat["lore_g_013"] = LoreEntry(
        lore_id="G-013",
        name="Geography / Резервации Гро",
        category="МЕСТО",
        description="Резервации Гро — отдельные поселения народов Гро за пределами Грани. Костеград — столица (построен на месте древней битвы Анхари и Гро). Также: орки в степях, тролли в горах, огры в болотах. Управляются имперскими чиновниками, без автономии.",
        when_to_apply="Квесты в резервациях, революционные сети, культура Гро",
        notes="Резервации ≠ провинция с правительством. Это оккупированные территории",
    )
    cat["lore_g_014"] = LoreEntry(
        lore_id="G-014",
        name="Geography / Пустыня Смерти",
        category="МЕСТО",
        description="Великая Пепельная Пустошь: пепел, сажа, кости, обломки наземных кораблей Анхари. Небо всегда серое, воздух тяжёлый с привкусом гари. Мёртвая тишина, нарушаемая воем ветра. Температура: обжигающая жара днём, ледяной холод ночью.",
        when_to_apply="Путешествия по Пустыне, атмосфера, квесты в руинах",
        notes="Пустыня ≠ просто опасное место. Это кладбище цивилизации Анхари — каждый слой пепла это история",
    )
    cat["lore_g_015"] = LoreEntry(
        lore_id="G-015",
        name="Geography / Пепельный Рубеж",
        category="МЕСТО",
        description="Пепельный Рубеж — зона вечных пепельных бурь глубоко в Пустыне. Видимость ноль, ветер до 150 км/ч, густой пепел забивает дыхание и механизмы, магические аномалии (компасы сходят с ума, время течёт неравномерно, появляются галюцинации).",
        when_to_apply="Переход через Пустыню, столкновение с Рубежом",
        notes="Рубеж — ВРЕМЕННЫЙ барьер. Бури могут утихнуть. Некоторые маги уже чувствуют это",
    )
    cat["lore_u_001"] = LoreEntry(
        lore_id="U-001",
        name="Угроза / Орда Пепла — суть",
        category="УГРОЗА",
        description="Вечный Ужас — это бесконечная Орда нежити: пепельные зомби, упыри, вампиры. Порождены из душ погибших Анхари из пепла и костей. Нет лидера, нет цели, нет разума — чистая неостановимая сила разрушения. Может уничтожить целый наземный корабль-государство.",
        when_to_apply="Угроза с юга, разговоры о Пустыне",
        notes="Орду нельзя подчинить, договориться или убедить. Это стихия, не армия",
    )
    cat["lore_u_002"] = LoreEntry(
        lore_id="U-002",
        name="Угроза / Орда Пепла — сдерживание",
        category="УГРОЗА",
        description="Орда сдерживается Пепельным Рубежом: пепельные бури разрывают нежить на части. Ханы/Анхари посчитали это постоянным барьером. Но Рубеж — временный. Некоторые маги чувствуют, что бури утихают, Орда растёт. Пепельные зомби уже изредка забредают к заставам.",
        when_to_apply="Разговоры о безопасности, старые дозорные, тревожные знаки",
        notes="700 лет спокойствия создали ложное чувство безопасности. Угроза реальна",
    )
    cat["lore_u_003"] = LoreEntry(
        lore_id="U-003",
        name="Угроза / Пепельные зомби",
        category="СУЩЕСТВО",
        description="Пепельные зомби: гуманоидные фигуры без лиц, из пустых глазниц сыплется пепел. Медленные, но неостановимые толпы. Поодиночке слабы — опасны массой.",
        when_to_apply="Сцены в Пустыне, атаки на заставы,",
        notes="Один зомби — не проблема. Толпа из сотен — катастрофа",
    )
    cat["lore_u_004"] = LoreEntry(
        lore_id="U-004",
        name="Угроза / Пепельные упыри",
        category="СУЩЕСТВО",
        description="Пепельные упыри: тощие, непропроционально высокие существа с длинными руками и ногами, кора из пепла и костей. Быстрые, охотятся стаями, взбираются на стены и корабли.",
        when_to_apply="Патрули в Пустыне, атаки на заставы, засады",
        notes="Упырь — проблема для одиночки. Стая упырей — проблема для отряда",
    )
    cat["lore_u_005"] = LoreEntry(
        lore_id="U-005",
        name="Угроза / Пепельные вампиры",
        category="СУЩЕСТВО",
        description="Пепельные вампиры: покрыты чёрной сажей, светящиеся красные глаза. Превращают жертв в пепельных зомби. Умнее других нежитей, координируют атаки, окружают жертв.",
        when_to_apply="Редкие, но опасные столкновения. Боссы для группы",
        notes="Единственная нежить с зачатками интеллекта. Их появление — плохой знак",
    )
    cat["lore_u_006"] = LoreEntry(
        lore_id="U-006",
        name="Угроза / Цикличность истории",
        category="НАРРАТИВ",
        description="Мотив цикличности: Анхари уничтожили свою цивилизацию жадностью → родилась Орда Пепла или \"Великий Ужас\". Грохания повторяет те же ошибки: эксплуатирует Гро, истощает ресурсы, игнорирует предупреждения. Вопрос: если Грохания падёт — появится ли новая Орда из новых мертвецов?",
        when_to_apply="Философские разговоры, квесты с экологическими темами, финальные акты",
        notes="Цикличность — главная мета-тема мира. Нарратор должен намекать на неё, не называя прямо",
    )
    cat["lore_m_001"] = LoreEntry(
        lore_id="M-001",
        name="Магия / Индустриальная",
        category="МАГИЯ",
        description="Магия в Грохании рациональна и дорога. Не творит чудеса из воздуха и не может сама добыть тонну угля. Использование: зачарованные кузнечные горны (чтобы не перегревались), руны на поршнях, телеграфная связь через кристаллы, магические щиты на кораблях.",
        when_to_apply="Любая технология с магическим компонентом, маги-инженеры",
        notes="Промышленная магия ≠ могущественная. Она деградировала от гармонии с природой до обслуживания фабрик",
    )
    cat["lore_m_002"] = LoreEntry(
        lore_id="M-002",
        name="Магия / Истощение источников",
        category="МАГИЯ",
        description="Магические источники в Грохании истощаются. Маги-инженеры стоят дорого. Некоторые маги чувствуют нарастающий «магический голод». Это параллельно ресурсному истощению Анхари, только вместо земли — магия.",
        when_to_apply="Маги-NPC, проблемы с зачарованием, дорогие магические услуги",
        notes="Истощение магии = ещё один признак цикличного падения. Нарратор может намекать на связь",
    )
    cat["lore_m_003"] = LoreEntry(
        lore_id="M-003",
        name="Магия / Шаманизм Севера",
        category="МАГИЯ",
        description="Шаманизм Вьюжных Пределов: духи предков, лёд, ветер, животные. Шаманы — уважаемые фигуры в кланах, общаются с духами природы. Жители центральной провинции (Грани) называют это, как и любую магию, «дикарством».",
        when_to_apply="Квесты с шаманами, духи природы, север",
        notes="Шаманизм ≠ слабая магия. В своих условиях — мощнее индустриальной. Но умирает без передачи знаний",
    )
    cat["lore_m_004"] = LoreEntry(
        lore_id="M-004",
        name="Магия / Природная магия Тенелесья",
        category="МАГИЯ",
        description="Лесная магия: лечение, управление растениями, общение с животными, защита леса. Кристаллы из магических источников — главный экспортный ресурс. Maгическое дерево (не горит, не гниёт) — вершина лесной магии. Жители центральной провинции (Грани) называют это, как и любую магию, «дикарством».",
        when_to_apply="Тенелесье, зелья, амулеты, лечение",
        notes="Лесная магия угасает из-за кислотных дождей из Грани. Через 50 лет может исчезнуть",
    )
    cat["lore_m_005"] = LoreEntry(
        lore_id="M-005",
        name="Магия / Технологии Анхари",
        category="МАГИЯ",
        description="Магии Анхари никогда не существовало, так как народы ее не практиковали и опирались на технологии. С момента объединания с народом Гро, появились первые представители людей практикующие магию. Тем не менее в широких массах увлечение магией среди жителей центральной правинции считается \"Анохронизмом\" и \"Варварством\"",
        when_to_apply="Артефакты в Пустыне, древние тексты, маги-историки",
        notes="Артефакты Анхари - это древние, утеренные технологии. Поэтому они ценная контрабанда",
    )
    cat["lore_e_001"] = LoreEntry(
        lore_id="E-001",
        name="Экономика / Деньги в столице",
        category="ЭКОНОМИКА",
        description="30 золотых (30g) в богатых кварталах Аники = чашка кофе и газета. В средних кварталах = скромный ужин на двоих. В гетто Гро = 1 неделя еды для семьи орков. В Пустыне Смерти = защитная маска (5g) + фляга воды (3g) + зачарованный компас (15g).",
        when_to_apply="Торговые сцены, подкуп, экономические решения",
        notes="Ценность денег полностью зависит от района и контекста",
    )
    cat["lore_e_002"] = LoreEntry(
        lore_id="E-002",
        name="Экономика / Чёрный рынок",
        category="ЭКОНОМИКА",
        description="На чёрном рынке за 30g можно купить: запрещённую книгу об истории Анхари, символ Культа Бурь (серебряная молния), пачку революционных листовок, поддельные документы с изменённым происхождением, контрабандный стим-пистолет.",
        when_to_apply="Чёрный рынок, нелегальные сделки, политические квесты",
        notes="Запрещённые предметы = политический риск при обнаружении",
    )
    cat["lore_e_003"] = LoreEntry(
        lore_id="E-003",
        name="Экономика / Промышленность Грани",
        category="ЭКОНОМИКА",
        description="Экономика Грани: добыча угля, железа, меди → производство стали, паровых машин, оружия, текстиля, химикатов. Рабочая сила: орки и тролли — тяжёлые работы, грохонцы — инженеры и надзиратели, люди — управление и торговля.",
        when_to_apply="Заводы, шахты, экономические конфликты, условия труда",
        notes="Экономика Грани держится на эксплуатации Гро. Без них — коллапс",
    )
    cat["lore_e_004"] = LoreEntry(
        lore_id="E-004",
        name="Экономика / Торговля провинций",
        category="ЭКОНОМИКА",
        description="Торговые потоки: Север (Вьюга) поставляет пушнину, древесину, редкие минералы → получает оружие, ткани, инструменты. Запад (Тенелесье) поставляет магическую древесину, зелья, кристаллы → получает металл, инструменты, предметы роскоши и \"гарантию безопасности\" для лесов.",
        when_to_apply="Торговые квесты, контрабанда, экономические конфликты",
        notes="Обе провинции зависят от торговли с Гранью. Это рычаг давления империи",
    )
    cat["lore_e_005"] = LoreEntry(
        lore_id="E-005",
        name="Экономика / Заставы",
        category="ЭКОНОМИКА",
        description="Экономика застав Пепельного Дозора полностью зависит от имперских субсидий. Дополнительный доход: добыча редких минералов и артефактов из Пустыни (опасно, но прибыльно). Если субсидии прекратятся — заставы развалятся за год.",
        when_to_apply="Финансирование застав, риск добычи в Пустыне, коррупция",
        notes="Именно зависимость от субсидий делает заставы удобным инструментом олигархов",
    )
    cat["lore_e_006"] = LoreEntry(
        lore_id="E-006",
        name="Экономика / Условия труда Гро",
        category="ЭКОНОМИКА",
        description="Условия труда Гро: орки и тролли получают минимальную оплату или только еду и кров. Огры работают бесплатно. Гоблины ввиду своего слабого телосложения работать в шахтах и заводах не могут, поэтому им ничего не остается кроме занятий криминала, попрошайничества и выполнения мелких поручений, вроде работы курьера. Гетто: перенаселение, болезни, преступность. Рабочий день без ограничений. Охрана из Культа Бурь жестоко подавляет любые протесты.",
        when_to_apply="Завод, шахта, условия в гетто, забастовки",
        notes="Это де-факто рабство при формальной свободе. Именно это питает революцию",
    )
    cat["lore_t_001"] = LoreEntry(
        lore_id="T-001",
        name="Термины / Официальные",
        category="КОНТЕКСТ",
        description="Официально в документах, судах, газетах: все граждане — «Грохонцы». Рас не существует. Слова «Анхари», «Ханы», «Гро» запрещены: первое нарушение — штраф, второе — тюрьма, третье — казнь. Применяется избирательно против политически неугодных.",
        when_to_apply="Бюрократические сцены, суды, официальные документы",
        notes="Закон есть, но все его нарушают. Опасность — в избирательном применении",
    )
    cat["lore_t_002"] = LoreEntry(
        lore_id="T-002",
        name="Термины / Бытовые",
        category="КОНТЕКСТ",
        description="В быту (таверны, рынки, дома): Люди зовут себя «люди». Орки = «зелёные», «клыкастые». Тролли = «длиннорукие», «серые». Огры = «тупые», «горы мяса». Грохонцы = «сплав», «ржавь», «полукровки». Культ Бурь = «буревестники», «молнии». Революционеры = «красные», «искры». Гоблины = «зеленые крысы»",
        when_to_apply="Неформальные разговоры, таверны, рынки, конфликты",
        notes="Эти слова формально запрещены, но полиция не реагирует в быту — только когда политически удобно",
    )
    cat["lore_t_003"] = LoreEntry(
        lore_id="T-003",
        name="Термины / Националистические",
        category="КОНТЕКСТ",
        description="Националисты используют слово «Анхари» — запрещённое древнее имя людей. Девиз: «Анхари превыше всего!» (за это казнят). Члены Культа Бурь называют себя «Истинными Сынами Пустыни» или «Народом Бури».",
        when_to_apply="Политические манифесты, вербовка в Культ, разговоры о величии Анхари",
        notes="«Анхари» произнесённое вслух = немедленный политический сигнал",
    )
    cat["lore_t_004"] = LoreEntry(
        lore_id="T-004",
        name="Термины / Революционные",
        category="КОНТЕКСТ",
        description="Революционеры используют слово «Гро» — запрещённое собирательное название для орков, троллей и огров. Это само по себе политический акт. Лозунг: «Гро — едины!». «Ханы» используют как обозначение угнетателей.",
        when_to_apply="Подпольные встречи, листовки, граффити в гетто",
        notes="Сказать «Гро» в политическом контексте = объявить себя революционером",
    )
    cat["lore_t_005"] = LoreEntry(
        lore_id="T-005",
        name="Термины / Выбор слова как механика",
        category="ГЕЙМПЛЕЙ",
        description="Выбор слова при обращении меняет реакцию NPC. К стражнику-члену Культа: «гражданин Грохонец» (официально, холодно) vs «человек» (бытово, по-свойски) vs «Анхари» (риск конфликта ИЛИ уважение, если он сам из Культа). Это ключевой социальный механизм.",
        when_to_apply="Любые переговоры, убеждение, дипломатия, вербовка",
        notes="Нарратор должен реагировать на слова игрока, а не только на намерение",
    )
    cat["lore_a_001"] = LoreEntry(
        lore_id="A-001",
        name="Атмосфера / Грань — запахи и виды",
        category="АТМОСФЕРА",
        description="Грань: небо серое от смога, идёт кислотный дождь, в воздухе запах угля и пара. Ночью небо светится от доменных печей. Паровые трубы везде. Дирижабли с имперскими флагами над головой. Внизу — грязь и копоть гетто.",
        when_to_apply="Описание сцены в Грани, первое впечатление от города",
        notes="Контраст: Верхние Грани — чистый воздух и мрамор. Нижние — копоть и болезни",
    )
    cat["lore_a_002"] = LoreEntry(
        lore_id="A-002",
        name="Атмосфера / Пустыня — ощущения",
        category="АТМОСФЕРА",
        description="Пустыня Смерти: воздух тяжёлый, привкус гари на языке. Пепел хрустит под ногами как снег. Мёртвая тишина, только вой ветра. Днём — обжигающая жара, ночью — ледяной холод. Запах гари и древней магии. Скелеты в пепле — остатки людей и кораблей.",
        when_to_apply="Путешествие по Пустыне, атмосфера юга",
        notes="Пепел — это буквально прах цивилизации. Нарратор может напоминать об этом",
    )
    cat["lore_a_003"] = LoreEntry(
        lore_id="A-003",
        name="Атмосфера / Гетто — быт",
        category="БЫТ",
        description="Быт гетто Гро: трущобы, бараки, землянки. Рваньё и рабочая одежда. Орки поют песни о свободе (устные эпосы). Тролли устраивают простые ритуалы поклонения силе. Пахнет машинным маслом, потом, варёными бобами. Дети орков играют в грязи между железными бочками.",
        when_to_apply="Сцены в гетто, встречи с Гро, революционная агитация",
        notes="Гетто — не только нищета. Там есть культура, юмор, взаимопомощь и надежда",
    )
    cat["lore_a_004"] = LoreEntry(
        lore_id="A-004",
        name="Атмосфера / Таверна в промзоне",
        category="БЫТ",
        description="Типичная таверна в Нижних Гранях: прокопчённые стены, мутное пиво, тусклые газовые лампы. За стойкой — грохонец. В углу — орки после смены в шахте. У окна — человек в потёртом сюртуке читает запрещённый памфлет. Кто-то вполголоса называет кого-то «зелёным» — назревает драка.",
        when_to_apply="Завязка конфликта, встречи с NPC, социальная атмосфера",
        notes="Таверна — место где официальный мир и реальный мир сталкиваются",
    )
    cat["lore_a_005"] = LoreEntry(
        lore_id="A-005",
        name="Атмосфера / Вьюга — север",
        category="АТМОСФЕРА",
        description="Ледоград: крепости из чёрного камня и деревянные дома с резными узорами, большие гостевые дома похожие на перевернутые корабли. Запах дыма из печей, оленьих шкур, хвои. Северяне в мехах и кожаных плащах с топорами. Шаман с посохом из костей. Олени запряжены в сани. Зимой — лыжи, пурга, снег до пояса.",
        when_to_apply="Сцены на севере, Ледоград, встречи с северянами",
        notes="Север = жизнь в суровых условиях, но с достоинством. Не нищета",
    )
    cat["lore_a_006"] = LoreEntry(
        lore_id="A-006",
        name="Атмосфера / Тенелесье",
        category="АТМОСФЕРА",
        description="Тенелесье: полумрак даже днём — свет едва пробивается через кроны. Запах смолы, трав, влажной земли. Мосты из живых лиан между деревьями. Эльфы бесшумно движутся в ветвях. Иногда — вспышка нимфы у ручья. Тишина леса прерывается только птицами.",
        when_to_apply="Тенелесье, встречи с лесными жителями, магические квесты",
        notes="Чем глубже в лес — тем меньше следов человека и тем сильнее магия",
    )
    cat["lore_a_007"] = LoreEntry(
        lore_id="A-007",
        name="Атмосфера / Застава у Пустыни",
        category="АТМОСФЕРА",
        description="Застава Пепельного Дозора: крепость из чёрного камня в серой пыли. Дозорные в пыльных плащах с капюшонами и масками с огромными очками. Пахнет пеплом и алкоголем. Ночью — сигнальные огни на башнях. В казарме — карты и кости, разговоры в пол голоса о странностях на горизонте. Кто-то смотрит на Пустыню часами.",
        when_to_apply="Южные квесты, заставы, атмосфера безнадёжного дозора",
        notes="Атмосфера застав = скука + страх + ощущение брошенности. Гремучая смесь",
    )
    cat["lore_n_001"] = LoreEntry(
        lore_id="N-001",
        name="Нарратив / Главная тема",
        category="НАРРАТИВ",
        description="Главная тема мира: цикличность. История повторяется. Анхари уничтожили себя жадностью. Грохания повторяет их путь. Знание об этом есть — но его замалчивают. Вопрос не «что произойдёт», а «сможет ли кто-то разорвать цикл».",
        when_to_apply="Любые квесты с историческим или экологическим подтекстом",
        notes="Нарратор намекает на цикличность через детали: разрушенные корабли = разрушенные заводы",
    )
    cat["lore_n_002"] = LoreEntry(
        lore_id="N-002",
        name="Нарратив / Кто виноват",
        category="НАРРАТИВ",
        description="Ключевой нарративный вопрос: кто настоящий враг? Не орки и не националисты. Реальный источник проблем — Совет Анхари, который намеренно стравил народы. Но большинство NPC этого не знают и винят «тех, кто рядом».",
        when_to_apply="Политические разговоры, моральные дилеммы, поиск виновных",
        notes="Нарратор не должен прямо называть Совет виновником — это должны открыть игроки",
    )
    cat["lore_n_003"] = LoreEntry(
        lore_id="N-003",
        name="Нарратив / Моральные дилеммы",
        category="НАРРАТИВ",
        description="Мир намеренно избегает чёрно-белой морали: Культ Бурь — жертвы, ставшие палачами. Революционеры применяют террор. Олигархи не садисты — просто холодные прагматики. Монарх — не злодей, а слепой человек. Старая аристократия — бессильные свидетели.",
        when_to_apply="Любой значимый выбор игроков, встречи с лидерами фракций",
        notes="Нарратор должен показывать внутреннюю логику КАЖДОЙ стороны, не осуждая её",
    )
    cat["lore_n_004"] = LoreEntry(
        lore_id="N-004",
        name="Нарратив / Память и забвение",
        category="НАРРАТИВ",
        description="Центральный нарративный конфликт: Закон о Забвении стёр имена народов, но память жива. Старики помнят. Барды поют. Тайные книги хранятся. Восстановить историю — значит дать народам Гро их идентичность. Но это дестабилизирует Империю.",
        when_to_apply="Квесты с архивами, старые книги, разговоры с пожилыми NPC",
        notes="«Анхари» как слово — оружие. Тот, кто контролирует историю, контролирует будущее",
    )
    cat["lore_n_005"] = LoreEntry(
        lore_id="N-005",
        name="Нарратив / Цена порядка",
        category="НАРРАТИВ",
        description="Базовый конфликт: Революция обещает свободу, но принесёт хаос, кровь и разрушения. Порядок империи держится на рабстве и лжи. Оба варианта — плохие. Третий путь — реформы — блокируется Советом Анхари. Игроки должны выбирать.",
        when_to_apply="Финальные решения, политические квесты, выбор стороны",
        notes="Нет правильного ответа. Нарратор не должен навязывать",
    )
    cat["lore_n_006"] = LoreEntry(
        lore_id="N-006",
        name="Нарратив / Слово как акт",
        category="НАРРАТИВ",
        description="В этом мире слово = политический акт. Сказать «Гро» вслух — революция. Сказать «Анхари» — фашизм. Сказать «Грохонцы» — конформизм. Игроки могут использовать язык как оружие, щит или ключ к разным NPC.",
        when_to_apply="Все социальные взаимодействия",
        notes="Нарратор должен активно реагировать на СЛОВА игроков, не только их действия",
    )
    cat["lore_gm_02"] = LoreEntry(
        lore_id="GM-02",
        name="Механика / Фракции и последствия",
        category="ГЕЙМПЛЕЙ",
        description="Поддержка одной фракции автоматически ухудшает отношения с другой. Культ Бурь vs Революционеры — взаимоисключающие союзники. Совет Анхари манипулирует обеими сторонами. Нейтральная позиция возможна, но трудна — обе стороны будут давить на выбор.",
        when_to_apply="Любое значимое решение игроков",
        notes="Совет Анхари — единственная фракция, которая остаётся в тени. Открытый союз с ними невозможен",
    )
    cat["lore_gm_03"] = LoreEntry(
        lore_id="GM-03",
        name="Механика / ЧА (харизма) в этом мире",
        category="ГЕЙМПЛЕЙ",
        description="Харизма в Грохании = политическая агитация. Лидер Культа использует харизму для настройки толпы против орков. Революционер — для подъёма на баррикады. Олигарх — для подкупа. Выбор слов и термина (официальный vs бытовой vs запрещённый) добавляет бонус или штраф.",
        when_to_apply="Все социальные броски с Харизмой",
        notes="Харизма-броски в этом мире всегда политически окрашены",
    )
    cat["lore_gm_04"] = LoreEntry(
        lore_id="GM-04",
        name="Механика / Случайные события",
        category="ГЕЙМПЛЕЙ",
        description="Примеры случайных событий: Националист требует выгнать грохонца-торговца из лавки (но сосед заступается). Тролль-рабочий сбежал с завода — его ищут. Чиновник требует указать «национальность: Грохонец» в форме. Пьяный из Культа выкрикивает «Анхари!» в таверне — стражники должны реагировать.",
        when_to_apply="Генерация случайных событий в городе, заполнение мира жизнью",
        notes="Каждое событие должно иметь политическое измерение — это главная особенность мира",
    )

    session.add_all(list(cat.values()))
    session.flush()  # назначаем id (нужно для ссылки призыва)

    cat["necromancer"] = Creature(
        name="Некромант", description="Поднимает приспешников", is_unique=True, is_sentient=True,
        hp=22, dexterity=6, phys_defense=10, mag_defense=6, mental_defense=9,
        phys_damage_dice="1d6", strength=4, charisma=6, wisdom=8,
        abilities=[
            Ability(
                name="Зов мертвецов", description="В начале боя призывает двух скелетов",
                trigger=AbilityTrigger.ON_COMBAT_START.value, once_per_combat=True,
                actions=[{"type": ActionType.SUMMON.value, "creature_id": cat["skeleton"].id, "count": 2}],
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
