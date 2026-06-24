"""Метаданные категорий и форм для админ-UI.

Этот модуль — единый источник истины для:

* **категорий** просмотра карточек (герои / NPC и существа / предметы /
  способности), их фильтров и сортировок;
* **полей форм** добавления сущности — каждое поле несёт человекочитаемую
  подсказку (``hint``) и правила валидации, которые применяются и на фронтенде
  (живые подсказки), и на сервере (``validate_payload``).

Имена полей форм совпадают с именами колонок ORM, поэтому создание карточки —
это почти прямой ``Model(**cleaned)`` (см. ``repository.create_card``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..dice import Dice
from ..enums import CardType
from ..rules.validation import (
    BASE_STAT,
    DISTRIBUTION_POINTS,
    MIN_STAT,
    PointBuyError,
    validate_point_buy,
)


# ───────────────────────── поля форм ─────────────────────────


@dataclass
class FieldSpec:
    """Описание одного поля формы.

    ``type`` управляет и виджетом на фронте, и приведением/проверкой на сервере:
      * ``str`` — короткая строка;
      * ``text`` — многострочное описание;
      * ``int`` — целое (с опциональными ``min``/``max``);
      * ``bool`` — флажок;
      * ``dice`` — кубиковая нотация ``NdM`` (валидируется ``Dice.parse``);
      * ``choice`` — выбор из ``choices`` либо динамически из ``choices_source``.
    """

    name: str
    label: str
    type: str = "str"
    hint: str = ""
    required: bool = False
    default: Any = None
    min: Optional[int] = None
    max: Optional[int] = None
    choices: Optional[list[dict]] = None        # [{value, label}]
    choices_source: Optional[str] = None         # "weapons" | "armor" | ...
    allow_blank: bool = True                      # для dice/choice — можно пусто

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "hint": self.hint,
            "required": self.required,
            "default": self.default,
            "min": self.min,
            "max": self.max,
            "choices": self.choices,
            "choices_source": self.choices_source,
            "allow_blank": self.allow_blank,
        }


@dataclass
class FormSpec:
    """Форма создания карточки конкретного типа."""

    card_type: str
    label: str
    icon: str
    note: str
    fields: list[FieldSpec] = field(default_factory=list)
    # доп. валидация на уровне всей формы (напр. пойнт-бай персонажа)
    cross_validate: Optional[Callable[[dict, dict], None]] = None

    def to_dict(self) -> dict:
        return {
            "card_type": self.card_type,
            "label": self.label,
            "icon": self.icon,
            "note": self.note,
            "fields": [f.to_dict() for f in self.fields],
        }


# ───────────────────────── общие поля ─────────────────────────

_STAT_CHOICES = [
    {"value": "strength", "label": "Сила"},
    {"value": "dexterity", "label": "Ловкость"},
    {"value": "wisdom", "label": "Мудрость"},
    {"value": "charisma", "label": "Харизма"},
]


def _name_field() -> FieldSpec:
    return FieldSpec("name", "Название", "str", "Как карточка называется в игре", required=True)


def _description_field() -> FieldSpec:
    return FieldSpec("description", "Описание", "text", "Короткий лор/пояснение (необязательно)")


def _image_field() -> FieldSpec:
    return FieldSpec(
        "image_id", "Изображение", "str",
        "Имя файла арта в static/images/cards/ (например goblin.png). "
        "Если пусто — карточка покажет заглушку по типу.",
    )


def _price_field(hint: str = "Стоимость в монетах (целое ≥ 0)") -> FieldSpec:
    return FieldSpec("price", "Цена", "int", hint, min=0)


def _unique_field() -> FieldSpec:
    return FieldSpec("is_unique", "Уникальная", "bool", "Существует в мире в единственном экземпляре")


# ───────────────────────── кросс-валидация персонажа ─────────────────────────


def _validate_character(cleaned: dict, errors: dict) -> None:
    """Пойнт-бай характеристик для игрового персонажа (манифест §2)."""
    if not cleaned.get("is_player"):
        return  # NPC характеристиками не ограничен
    try:
        validate_point_buy(
            cleaned.get("base_strength", BASE_STAT),
            cleaned.get("base_dexterity", BASE_STAT),
            cleaned.get("base_wisdom", BASE_STAT),
            cleaned.get("base_charisma", BASE_STAT),
        )
    except PointBuyError as exc:
        errors["__form__"] = (
            f"Распределение характеристик нарушает пойнт-бай: {exc}. "
            f"База {BASE_STAT}, +{DISTRIBUTION_POINTS} очков на четыре характеристики, "
            f"минимум {MIN_STAT}."
        )


# ───────────────────────── формы по типам карточек ─────────────────────────


def _build_forms() -> dict[str, FormSpec]:
    pointbuy_hint = (
        f"База {BASE_STAT}. У игрока +{DISTRIBUTION_POINTS} очков суммарно "
        f"(минимум {MIN_STAT}); у NPC — без ограничений."
    )
    forms: dict[str, FormSpec] = {}

    forms[CardType.CHARACTER.value] = FormSpec(
        card_type=CardType.CHARACTER.value,
        label="Персонаж",
        icon="🧝",
        note="Игрок (PC) или мастерский (NPC). Атрибуты (HP, защиты) движок "
             "считает сам по характеристикам и снаряжению.",
        cross_validate=_validate_character,
        fields=[
            _name_field(),
            _description_field(),
            FieldSpec("is_player", "Игровой персонаж (PC)", "bool",
                      "Включено — действует пойнт-бай; выключено — это NPC.", default=True),
            FieldSpec("is_sentient", "Разумный", "bool",
                      "Влияет на устрашение/переговоры (§12).", default=True),
            FieldSpec("base_strength", "Сила", "int", pointbuy_hint, default=BASE_STAT, min=1),
            FieldSpec("base_dexterity", "Ловкость", "int", pointbuy_hint, default=BASE_STAT, min=1),
            FieldSpec("base_wisdom", "Мудрость", "int", pointbuy_hint, default=BASE_STAT, min=1),
            FieldSpec("base_charisma", "Харизма", "int", pointbuy_hint, default=BASE_STAT, min=1),
            FieldSpec("money", "Деньги", "int", "Монеты на руках", default=0, min=0),
            FieldSpec("current_hp", "Текущие HP", "int",
                      "Пусто — полные HP от максимума.", min=0),
            FieldSpec("equipped_weapon_id", "Оружие", "choice",
                      "Экипированное оружие (из существующих карточек).",
                      choices_source="weapons"),
            FieldSpec("equipped_armor_id", "Броня", "choice",
                      "Экипированная броня (из существующих карточек).",
                      choices_source="armor"),
            _image_field(),
        ],
    )

    forms[CardType.CREATURE.value] = FormSpec(
        card_type=CardType.CREATURE.value,
        label="Существо",
        icon="👹",
        note="Монстр/существо. Защиты задаются напрямую (не через Ловкость).",
        fields=[
            _name_field(),
            _description_field(),
            FieldSpec("is_sentient", "Разумное", "bool",
                      "Можно ли устрашать/договариваться (§12).", default=False),
            _unique_field(),
            FieldSpec("hp", "HP", "int", "Очки здоровья (≥ 1)", default=1, min=1, required=True),
            FieldSpec("dexterity", "Ловкость", "int", "Для инициативы", default=0, min=0),
            FieldSpec("phys_defense", "Физ. защита", "int", "Порог попадания физ. атаки", default=0, min=0),
            FieldSpec("mag_defense", "Маг. защита", "int", "Спасбросок против заклинаний", default=0, min=0),
            FieldSpec("mental_defense", "Мент. защита", "int", "Сопротивление ментальным атакам", default=0, min=0),
            FieldSpec("phys_damage_dice", "Урон (кубики)", "dice",
                      "Кубики урона в нотации NdM, например 1d8.", default="1d8", allow_blank=False),
            FieldSpec("strength", "Сила", "int", "Для устрашения/переговоров (§12)", default=0, min=0),
            FieldSpec("charisma", "Харизма", "int", "Для групповых механик (§12)", default=0, min=0),
            FieldSpec("wisdom", "Мудрость", "int", "Для переговоров (§12)", default=0, min=0),
            _image_field(),
        ],
    )

    forms[CardType.WEAPON.value] = FormSpec(
        card_type=CardType.WEAPON.value,
        label="Оружие",
        icon="⚔️",
        note="Карточка оружия. Урон — кубики; требования по Силе/Ловкости опциональны.",
        fields=[
            _name_field(),
            _description_field(),
            FieldSpec("damage_dice", "Урон (кубики)", "dice",
                      "Кубики урона NdM, например 1d8.", default="1d4", allow_blank=False),
            FieldSpec("str_requirement", "Требование Силы", "int", "Минимальная Сила (пусто — нет)", min=0),
            FieldSpec("dex_requirement", "Требование Ловкости", "int", "Минимальная Ловкость (пусто — нет)", min=0),
            FieldSpec("is_ranged", "Дальнобойное", "bool", "Лук/арбалет (для магических стрел и т.п.)", default=False),
            _price_field(),
            _unique_field(),
            _image_field(),
        ],
    )

    forms[CardType.ARMOR.value] = FormSpec(
        card_type=CardType.ARMOR.value,
        label="Броня",
        icon="🛡️",
        note="Карточка брони. Бонус физзащиты входит в формулу защиты владельца.",
        fields=[
            _name_field(),
            _description_field(),
            FieldSpec("phys_def_bonus", "Бонус физзащиты", "int", "Прибавка к физзащите", default=0, min=0),
            FieldSpec("str_requirement", "Требование Силы", "int", "Минимальная Сила (пусто — нет)", min=0),
            FieldSpec("dex_requirement", "Требование Ловкости", "int", "Минимальная Ловкость (пусто — нет)", min=0),
            _price_field(),
            _unique_field(),
            _image_field(),
        ],
    )

    forms[CardType.ITEM.value] = FormSpec(
        card_type=CardType.ITEM.value,
        label="Предмет",
        icon="🎒",
        note="Зелье, талисман, щит и прочее. Для зелий укажите кубики лечения.",
        fields=[
            _name_field(),
            _description_field(),
            FieldSpec("is_consumable", "Расходуемый", "bool", "Исчезает после применения", default=False),
            FieldSpec("heal_dice", "Лечение (кубики)", "dice",
                      "Для зелий — кубики хила NdM (например 2d4). Иначе пусто."),
            _price_field(),
            _unique_field(),
            _image_field(),
        ],
    )

    spell_fields = lambda: [  # noqa: E731 — компактно, общий набор для тома и свитка
        _name_field(),
        _description_field(),
        FieldSpec("spell_name", "Заклинание", "str", "Название заклинания", required=True),
        FieldSpec("damage_dice", "Урон (кубики)", "dice",
                  "Кубики урона заклинания NdM, например 1d10.", allow_blank=False, required=True),
        FieldSpec("heal_dice", "Лечение (кубики)", "dice", "Если заклинание лечит — кубики NdM."),
        FieldSpec("difficulty", "Сложность активации", "int",
                  "Порог броска активации (d20 + бонус ≥ сложности).", required=True, min=1),
        FieldSpec("attack_stat", "Характеристика атаки", "choice",
                  "Какая характеристика бьёт заклинанием.", default="wisdom", choices=_STAT_CHOICES),
        _price_field(),
        _unique_field(),
        _image_field(),
    ]

    forms[CardType.SPELLBOOK.value] = FormSpec(
        card_type=CardType.SPELLBOOK.value,
        label="Том магии",
        icon="📖",
        note="Носитель одного заклинания, многоразовый.",
        fields=spell_fields(),
    )
    forms[CardType.SCROLL.value] = FormSpec(
        card_type=CardType.SCROLL.value,
        label="Свиток",
        icon="📜",
        note="Носитель одного заклинания, одноразовый (исчезает после применения).",
        fields=spell_fields(),
    )

    forms[CardType.INSTRUMENT.value] = FormSpec(
        card_type=CardType.INSTRUMENT.value,
        label="Инструмент",
        icon="🪕",
        note="Немагические групповые способности (лютня, барабан). Способности "
             "пока добавляются через сид; здесь — базовая карточка.",
        fields=[
            _name_field(),
            _description_field(),
            _price_field(),
            _unique_field(),
            _image_field(),
        ],
    )

    forms[CardType.SKILL.value] = FormSpec(
        card_type=CardType.SKILL.value,
        label="Навык",
        icon="🎓",
        note="Навык покупается за деньги, остаётся с персонажем навсегда, его "
             "нельзя продать и он НЕ занимает слот инвентаря. Механика как у тома: "
             "заполните поля заклинания для активного навыка-каста. Навыки-способности "
             "(бафф/дебафф) пока задаются через сид.",
        fields=[
            _name_field(),
            _description_field(),
            FieldSpec("is_passive", "Пассивный", "bool",
                      "Пассивный навык (постоянные эффекты) vs активный (каст/активация).",
                      default=False),
            _price_field("Стоимость покупки навыка (целое ≥ 0)"),
            FieldSpec("spell_name", "Заклинание", "str",
                      "Название заклинания навыка (для активного навыка-каста)."),
            FieldSpec("damage_dice", "Урон (кубики)", "dice",
                      "Кубики урона заклинания NdM, например 4d4. Пусто — навык не кастует."),
            FieldSpec("heal_dice", "Лечение (кубики)", "dice", "Если навык лечит — кубики NdM."),
            FieldSpec("difficulty", "Сложность активации", "int",
                      "Порог броска активации заклинания (нужен для каста).", min=1),
            FieldSpec("attack_stat", "Характеристика атаки", "choice",
                      "Какой характеристикой кастует навык.", default="wisdom", choices=_STAT_CHOICES),
            _image_field(),
        ],
    )

    return forms


CARD_FORMS: dict[str, FormSpec] = _build_forms()


# ───────────────────────── категории просмотра ─────────────────────────


@dataclass
class Category:
    """Категория витрины карточек: какие типы показывать, чем фильтровать/сортировать."""

    key: str
    label: str
    icon: str
    card_types: list[str]
    # фильтры: [{value, label, card_types?}] — первый всегда «все»
    filters: list[dict] = field(default_factory=list)
    # сортировки: [{value(=поле), label}]
    sorts: list[dict] = field(default_factory=list)
    # какие типы карточек можно создавать в этой категории
    creatable: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "icon": self.icon,
            "card_types": self.card_types,
            "filters": self.filters,
            "sorts": self.sorts,
            "creatable": self.creatable,
        }


CATEGORIES: list[Category] = [
    Category(
        key="heroes",
        label="Герои",
        icon="🧝",
        card_types=[CardType.CHARACTER.value],  # отбор по is_player=True — в репозитории
        sorts=[
            {"value": "name", "label": "По имени"},
            {"value": "money", "label": "По деньгам"},
        ],
        creatable=[CardType.CHARACTER.value],
    ),
    Category(
        key="npc",
        label="NPC и существа",
        icon="👹",
        card_types=[CardType.CHARACTER.value, CardType.CREATURE.value],
        filters=[
            {"value": "all", "label": "Все"},
            {"value": CardType.CHARACTER.value, "label": "Персонажи (NPC)"},
            {"value": CardType.CREATURE.value, "label": "Существа"},
        ],
        sorts=[
            {"value": "name", "label": "По имени"},
            {"value": "hp", "label": "По HP"},
        ],
        creatable=[CardType.CREATURE.value, CardType.CHARACTER.value],
    ),
    Category(
        key="items",
        label="Предметы",
        icon="🎒",
        card_types=[
            CardType.WEAPON.value, CardType.ARMOR.value, CardType.ITEM.value,
            CardType.SPELLBOOK.value, CardType.SCROLL.value, CardType.INSTRUMENT.value,
        ],
        filters=[
            {"value": "all", "label": "Все"},
            {"value": CardType.WEAPON.value, "label": "Оружие"},
            {"value": CardType.ARMOR.value, "label": "Броня"},
            {"value": "other", "label": "Прочее",
             "card_types": [CardType.ITEM.value, CardType.SPELLBOOK.value,
                            CardType.SCROLL.value, CardType.INSTRUMENT.value]},
        ],
        sorts=[
            {"value": "name", "label": "По имени"},
            {"value": "price", "label": "По стоимости"},
        ],
        creatable=[
            CardType.WEAPON.value, CardType.ARMOR.value, CardType.ITEM.value,
            CardType.SPELLBOOK.value, CardType.SCROLL.value, CardType.INSTRUMENT.value,
        ],
    ),
    Category(
        key="skills",
        label="Навыки",
        icon="🎓",
        card_types=[CardType.SKILL.value],
        filters=[
            {"value": "all", "label": "Все"},
            {"value": "active", "label": "Активные"},
            {"value": "passive", "label": "Пассивные"},
        ],
        sorts=[
            {"value": "name", "label": "По имени"},
            {"value": "price", "label": "По стоимости"},
        ],
        creatable=[CardType.SKILL.value],
    ),
    Category(
        key="abilities",
        label="Способности",
        icon="✨",
        card_types=[],  # особая категория: это не карточки, а Ability
        sorts=[
            {"value": "name", "label": "По имени"},
            {"value": "chance", "label": "По шансу"},
        ],
        creatable=[],
    ),
]

CATEGORIES_BY_KEY: dict[str, Category] = {c.key: c for c in CATEGORIES}


# ───────────────────────── валидация payload формы ─────────────────────────


def _clean_value(spec: FieldSpec, raw: Any, errors: dict) -> Any:
    """Привести и проверить одно значение. Кладёт ошибку в ``errors[spec.name]``."""
    blank = raw is None or (isinstance(raw, str) and raw.strip() == "")

    if blank:
        if spec.required:
            errors[spec.name] = "Обязательное поле"
            return None
        if spec.type == "bool":
            return bool(spec.default)
        return spec.default

    if spec.type == "bool":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "on", "yes", "да")

    if spec.type == "int":
        try:
            value = int(str(raw).strip())
        except (TypeError, ValueError):
            errors[spec.name] = "Нужно целое число"
            return None
        if spec.min is not None and value < spec.min:
            errors[spec.name] = f"Минимум {spec.min}"
            return None
        if spec.max is not None and value > spec.max:
            errors[spec.name] = f"Максимум {spec.max}"
            return None
        return value

    if spec.type == "dice":
        text = str(raw).strip()
        try:
            Dice.parse(text)
        except ValueError:
            errors[spec.name] = "Кубики в формате NdM, кости d4/d6/d8/d10/d12/d20 (например 2d6)"
            return None
        return text

    if spec.type == "choice":
        text = str(raw).strip()
        if spec.choices is not None:
            allowed = {str(c["value"]) for c in spec.choices}
            if text not in allowed:
                errors[spec.name] = "Недопустимое значение"
                return None
            return text
        # choices_source — динамические id; репозиторий проверит существование
        try:
            return int(text)
        except (TypeError, ValueError):
            errors[spec.name] = "Нужно выбрать существующую карточку"
            return None

    # str / text
    return str(raw).strip()


def validate_payload(card_type: str, payload: dict) -> tuple[dict, dict]:
    """Проверить и привести данные формы.

    Возвращает ``(cleaned, errors)``. Если ``errors`` непустой — карточку не
    создаём. Ключ ``"__form__"`` — общая ошибка формы (напр. пойнт-бай).
    """
    form = CARD_FORMS.get(card_type)
    if form is None:
        return {}, {"__form__": f"Неизвестный тип карточки: {card_type!r}"}

    cleaned: dict = {}
    errors: dict = {}
    for spec in form.fields:
        value = _clean_value(spec, payload.get(spec.name), errors)
        # пустые необязательные значения не передаём в конструктор (берётся default ORM)
        if value is not None:
            cleaned[spec.name] = value

    if not errors and form.cross_validate is not None:
        form.cross_validate(cleaned, errors)

    return cleaned, errors
