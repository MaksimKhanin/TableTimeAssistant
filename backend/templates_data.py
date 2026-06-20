"""Built-in adventure templates seeded on first startup."""

BUILTIN_TEMPLATES = [
    {
        "title": "Классическое подземелье",
        "category": "dungeon",
        "gm_role": "Dungeon Master",
        "player_count": 2,
        "description": (
            "Небольшой городок Брэмблхолт на краю Серых гор охвачен паникой: из заброшенной "
            "шахты Корвус пропадают люди. Местные говорят о проклятии — и о несметных сокровищах "
            "дварфских королей, погребённых в глубинах. Герои нанялись расследовать исчезновения. "
            "В шахте их ждут ловушки, гоблины, и кое-что пострашнее в самых тёмных тоннелях."
        ),
        "characters_json": [
            {
                "name": "Дарин Железнорук", "race": "Dwarf", "char_class": "Fighter",
                "level": 3, "strength": 17, "dexterity": 10, "constitution": 16,
                "intelligence": 8, "wisdom": 10, "charisma": 8,
                "max_hp": 30, "armor_class": 17, "attack_bonus": 5, "damage_dice": "1d8+3",
                "abilities": "Второе дыхание, Всплеск действия, Боевой стиль: Оружие и щит",
                "background": "Бывший шахтёр, потерял отца в этих туннелях 10 лет назад.",
            },
            {
                "name": "Лира Быстрый Лист", "race": "Halfling", "char_class": "Rogue",
                "level": 3, "strength": 8, "dexterity": 18, "constitution": 12,
                "intelligence": 13, "wisdom": 11, "charisma": 14,
                "max_hp": 20, "armor_class": 14, "attack_bonus": 6, "damage_dice": "1d6+4",
                "abilities": "Скрытая атака 2d6, Хитрое действие, Знаток",
                "background": "Городская воровка, ищет артефакт дварфских королей для гильдии.",
            },
        ],
        "npcs_json": [
            {
                "name": "Горг Главный", "role": "Вожак гоблинов", "is_enemy": 1,
                "personality": "Трусливый, но жадный. Считает себя умнее всех, ошибается.",
                "voice_style": "Говорит в третьем лице о себе. «Горг хочет золота!»",
                "max_hp": 18, "armor_class": 13, "attack_bonus": 3, "damage_dice": "1d6+1",
            },
            {
                "name": "Старый Пикс", "role": "Дух шахтёра", "is_enemy": 0,
                "personality": "Призрак погибшего дварфа. Хочет покоя, но не может уйти без мести.",
                "voice_style": "Говорит медленно, с эхом. Использует устаревшие слова.",
                "max_hp": 10, "armor_class": 10, "attack_bonus": 0, "damage_dice": "1d4",
            },
        ],
    },
    {
        "title": "Тёмное фэнтези",
        "category": "dark",
        "gm_role": "Повествователь",
        "player_count": 2,
        "description": (
            "Королевство Валлар умирает медленной смертью. Король сошёл с ума после визита "
            "загадочного советника в чёрном. Урожай гниёт на корню. Люди исчезают ночами. "
            "Церковь молчит — её жрецы куплены или мертвы. Герои — последние, кто ещё не "
            "сдался. Тон: мрачный, никакого оптимизма. Победа даётся ценой жертв. "
            "Нет простых ответов, нет однозначных злодеев."
        ),
        "characters_json": [
            {
                "name": "Кейра Пепел", "race": "Human", "char_class": "Warlock",
                "level": 4, "strength": 9, "dexterity": 13, "constitution": 12,
                "intelligence": 15, "wisdom": 10, "charisma": 18,
                "max_hp": 26, "armor_class": 13, "attack_bonus": 6, "damage_dice": "1d10+4",
                "abilities": "Тёмное благословение, Взор дьявола, Магическая броня",
                "background": "Заключила пакт с сущностью в обмен на жизнь брата. Жалеет об этом.",
            },
            {
                "name": "Вольф без Имени", "race": "Human", "char_class": "Ranger",
                "level": 4, "strength": 14, "dexterity": 17, "constitution": 13,
                "intelligence": 11, "wisdom": 15, "charisma": 8,
                "max_hp": 32, "armor_class": 15, "attack_bonus": 5, "damage_dice": "1d8+3",
                "abilities": "Любимый враг: нежить, Двойной выстрел, Лесной скиталец",
                "background": "Охотник на монстров, потерял семью от нежити. Не доверяет магам.",
            },
        ],
        "npcs_json": [
            {
                "name": "Советник Моррен", "role": "Главный антагонист", "is_enemy": 1,
                "personality": (
                    "Манипулятор высшего класса. Никогда не угрожает открыто. "
                    "Искренне считает, что спасает мир своими методами."
                ),
                "voice_style": (
                    "Мягкий, почти отеческий тон. Называет героев по имени. "
                    "Всегда предлагает 'разумный выход'."
                ),
                "max_hp": 65, "armor_class": 14, "attack_bonus": 7, "damage_dice": "2d6+3",
            },
            {
                "name": "Сестра Марта", "role": "Жрица-отступница", "is_enemy": 0,
                "personality": "Знает правду о советнике, но боится. Измотана, пьёт.",
                "voice_style": "Говорит намёками. Никогда прямо — следят.",
                "max_hp": 14, "armor_class": 10, "attack_bonus": 0, "damage_dice": "1d4",
            },
        ],
    },
    {
        "title": "Морские разбойники",
        "category": "sea",
        "gm_role": "Рассказчик морских легенд",
        "player_count": 3,
        "description": (
            "Карибское море XVI века, но с магией и морскими монстрами. "
            "Герои — команда вольного брига «Ярость шторма». Они только что захватили "
            "испанский галеон с картой к Острову Вечного Шторма, где, по легенде, "
            "покоится флот затопленного бога моря. Колониальные власти и конкурирующие "
            "пираты идут по пятам. Тон: авантюрный, с юмором, но с настоящими ставками."
        ),
        "characters_json": [
            {
                "name": "Капитан Роза Шторм", "race": "Human", "char_class": "Fighter",
                "level": 4, "strength": 15, "dexterity": 16, "constitution": 14,
                "intelligence": 12, "wisdom": 10, "charisma": 17,
                "max_hp": 36, "armor_class": 15, "attack_bonus": 6, "damage_dice": "1d8+4",
                "abilities": "Боевой стиль: Два оружия, Всплеск действия, Харизма капитана",
                "background": "Бывший морской офицер, уволена за отказ расстрелять пленников.",
            },
            {
                "name": "Джек Пустые Карманы", "race": "Gnome", "char_class": "Bard",
                "level": 4, "strength": 7, "dexterity": 15, "constitution": 10,
                "intelligence": 14, "wisdom": 12, "charisma": 18,
                "max_hp": 22, "armor_class": 13, "attack_bonus": 6, "damage_dice": "1d6+4",
                "abilities": "Вдохновение барда d8, Слово исцеления, Контрочарование",
                "background": "Бывший корабельный торговец. Проиграл всё состояние в кости. Теперь поёт.",
            },
            {
                "name": "Тия Глубины", "race": "Tiefling", "char_class": "Warlock",
                "level": 4, "strength": 9, "dexterity": 13, "constitution": 12,
                "intelligence": 14, "wisdom": 10, "charisma": 17,
                "max_hp": 24, "armor_class": 13, "attack_bonus": 6, "damage_dice": "1d10+4",
                "abilities": "Морской покровитель, Водное дыхание, Зов глубин",
                "background": "Её семья погибла от шторма. Заключила пакт с духом океана.",
            },
        ],
        "npcs_json": [
            {
                "name": "Адмирал Фернандо де Сильва", "role": "Охотник за пиратами", "is_enemy": 1,
                "personality": "Честь прежде всего. Ненавидит пиратов, но соблюдает правила войны.",
                "voice_style": "Формальный испанский акцент. Обращается к врагам с уважением.",
                "max_hp": 55, "armor_class": 18, "attack_bonus": 7, "damage_dice": "1d8+4",
            },
            {
                "name": "Старый Моряна", "role": "Штурман и навигатор", "is_enemy": 0,
                "personality": "Знает все моря. Суеверен до паранойи. Добр к тем, кто его уважает.",
                "voice_style": "Бурчит. Говорит пословицами и морскими поговорками.",
                "max_hp": 18, "armor_class": 11, "attack_bonus": 2, "damage_dice": "1d6",
            },
        ],
    },
    {
        "title": "Городская интрига",
        "category": "intrigue",
        "gm_role": "Рассказчик",
        "player_count": 2,
        "description": (
            "Имперская столица Аурум — центр власти, коррупции и тайных обществ. "
            "Великий Канцлер убит в запертой комнате своего особняка. Все улики ведут к "
            "герою. Чтобы выжить, надо найти настоящего убийцу раньше, чем стражники — "
            "героя. Социальные броски важнее боевых. Каждый NPC — и потенциальный союзник, "
            "и потенциальная угроза. Никому нельзя доверять полностью."
        ),
        "characters_json": [
            {
                "name": "Мира Дэйл", "race": "Half-Elf", "char_class": "Rogue",
                "level": 5, "strength": 10, "dexterity": 18, "constitution": 12,
                "intelligence": 16, "wisdom": 14, "charisma": 16,
                "max_hp": 30, "armor_class": 15, "attack_bonus": 7, "damage_dice": "1d6+4",
                "abilities": "Скрытая атака 3d6, Надёжный талант, Дипломатия",
                "background": "Бывший агент тайной канцелярии. Знает слишком много.",
            },
            {
                "name": "Профессор Эдин Вейл", "race": "Human", "char_class": "Wizard",
                "level": 5, "strength": 8, "dexterity": 12, "constitution": 11,
                "intelligence": 19, "wisdom": 16, "charisma": 11,
                "max_hp": 24, "armor_class": 12, "attack_bonus": 7, "damage_dice": "1d6+4",
                "abilities": "Знак провидца, Обнаружение мыслей, Хроника заклинаний",
                "background": "Историк и консультант канцелярии. Случайно оказался свидетелем.",
            },
        ],
        "npcs_json": [
            {
                "name": "Леди Арва", "role": "Наследница Канцлера", "is_enemy": 0,
                "personality": "Умна, холодна, grieving. Нанимает героев, но может предать ради власти.",
                "voice_style": "Краткие фразы. Никогда не говорит лишнего. Смотрит в глаза.",
                "max_hp": 12, "armor_class": 10, "attack_bonus": 0, "damage_dice": "1d4",
            },
            {
                "name": "Командир Страж Ортус", "role": "Охотник за героями", "is_enemy": 1,
                "personality": "Честный человек в нечестной системе. Верит в вину героев.",
                "voice_style": "Официальный, сухой. По имени — никогда, только 'подозреваемый'.",
                "max_hp": 40, "armor_class": 16, "attack_bonus": 6, "damage_dice": "1d8+3",
            },
        ],
    },
    {
        "title": "Хоррор: Туманный особняк",
        "category": "horror",
        "gm_role": "Голос из темноты",
        "player_count": 2,
        "description": (
            "Особняк Блэкхарт стоит на холме вот уже 200 лет. Каждые 30 лет кто-то "
            "входит внутрь. Никто не выходит. Герои застряли здесь в ночной шторм — "
            "мост размыло. До рассвета семь часов. Ужас атмосферный, не gore. "
            "Дом живёт. Комнаты меняются местами. Зеркала показывают прошлое. "
            "Что-то здесь очень голодное и очень терпеливое."
        ),
        "characters_json": [
            {
                "name": "Доктор Вейн Холлоу", "race": "Human", "char_class": "Cleric",
                "level": 4, "strength": 11, "dexterity": 12, "constitution": 13,
                "intelligence": 15, "wisdom": 18, "charisma": 12,
                "max_hp": 28, "armor_class": 13, "attack_bonus": 5, "damage_dice": "1d8+4",
                "abilities": "Изгнание нечисти, Духовное оружие, Слово исцеления",
                "background": "Исследователь паранормального. Пишет книгу о проклятых местах.",
            },
            {
                "name": "Нора Эш", "race": "Human", "char_class": "Fighter",
                "level": 4, "strength": 16, "dexterity": 13, "constitution": 15,
                "intelligence": 10, "wisdom": 11, "charisma": 9,
                "max_hp": 38, "armor_class": 14, "attack_bonus": 6, "damage_dice": "1d10+4",
                "abilities": "Второе дыхание, Всплеск действия, Несокрушимость",
                "background": "Ветеран. Не верит в призраков. Сильно ошибается.",
            },
        ],
        "npcs_json": [
            {
                "name": "Нечто", "role": "Хозяин особняка", "is_enemy": 1,
                "personality": (
                    "Древнее. Не злое в человеческом смысле — просто голодное. "
                    "Играет с жертвами, как кот с мышью."
                ),
                "voice_style": (
                    "Говорит голосами мёртвых. Иногда голосами живых, сидящих рядом. "
                    "Никогда не угрожает прямо."
                ),
                "max_hp": 80, "armor_class": 16, "attack_bonus": 8, "damage_dice": "2d8+4",
            },
            {
                "name": "Призрак Лили", "role": "Дочь первого владельца", "is_enemy": 0,
                "personality": "Умерла в 9 лет, застряла здесь. Боится Нечто. Хочет помочь.",
                "voice_style": "Детский голос. Говорит загадками, не понимает взрослых слов.",
                "max_hp": 5, "armor_class": 8, "attack_bonus": 0, "damage_dice": "1d4",
            },
        ],
    },
]
