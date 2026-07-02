"""ORM-модели «Гроханики» (SQLAlchemy 2.0).

Все игровые объекты — это *карточки* (манифест §1). Реализовано через
joined-table inheritance: общая таблица ``cards`` (id, тип, имя, арт,
уникальность) + отдельная таблица под каждый тип карточки. Так каждый тип
свободно описывает свои поля без «широкой» таблицы с кучей NULL.

Карточки шаблонны и переиспользуемы (одна «Кожаная броня» на нескольких
персонажей). Состояние конкретного боя живёт не здесь, а в ``engine.combatant``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ..enums import CardType


class Base(DeclarativeBase):
    """Базовый декларативный класс."""


# ───────────────────────── базовая карточка ─────────────────────────


class Card(Base):
    """Общий предок всех карточек.

    ``card_type`` — дискриминатор. ``image_id`` — ключ во внешнюю таблицу
    изображений (арт меняется без правки карточки, манифест §1).
    """

    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String, default="")
    image_id: Mapped[Optional[str]] = mapped_column(String(120), default=None)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=False)

    effects: Mapped[list["Effect"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        foreign_keys="Effect.owner_card_id",
    )
    abilities: Mapped[list["Ability"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        foreign_keys="Ability.owner_card_id",
    )

    __mapper_args__ = {
        "polymorphic_on": card_type,
        "polymorphic_identity": "card",
    }

    def __repr__(self) -> str:  # pragma: no cover - удобство отладки
        return f"<{type(self).__name__} id={self.id} name={self.name!r}>"


# ───────────────────────── эффекты ─────────────────────────


class Effect(Base):
    """Числовой модификатор stat/attr (манифест §5).

    Игрок видит только итоговые атрибуты. ``source_id`` из манифеста — это id
    карточки-владельца (``owner_card_id``).
    """

    __tablename__ = "effects"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_card_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cards.id"))

    description: Mapped[str] = mapped_column(String, default="")
    target_type: Mapped[str] = mapped_column(String(8))   # stat | attr
    target: Mapped[str] = mapped_column(String(24))
    modifier: Mapped[int] = mapped_column(Integer, default=0)
    duration: Mapped[int] = mapped_column(Integer, default=0)  # 0 = постоянный
    source_type: Mapped[str] = mapped_column(String(12))
    activation_source: Mapped[Optional[str]] = mapped_column(String(24), default=None)
    visible_to_player: Mapped[bool] = mapped_column(Boolean, default=False)
    is_stackable: Mapped[bool] = mapped_column(Boolean, default=True)

    owner: Mapped[Optional["Card"]] = relationship(
        back_populates="effects", foreign_keys=[owner_card_id]
    )

    @property
    def source_id(self) -> Optional[int]:
        """Псевдоним под терминологию манифеста (source_id == owner_card_id)."""
        return self.owner_card_id


# ───────────────────────── способности (data-driven) ─────────────────────────


class Ability(Base):
    """Уникальная способность по схеме «триггер → действия» (data-driven).

    ``actions`` — список словарей-действий, например::

        [{"type": "summon", "creature_id": 7, "count": 2}]
        [{"type": "instakill"}]

    Сами действия интерпретирует ``engine.abilities``. ``chance`` —
    вероятность срабатывания (например, мгновенное убийство по шансу).
    """

    __tablename__ = "abilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_card_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cards.id"))

    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String, default="")
    trigger: Mapped[str] = mapped_column(String(24))
    chance: Mapped[Optional[float]] = mapped_column(Float, default=None)
    once_per_combat: Mapped[bool] = mapped_column(Boolean, default=False)
    condition: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    actions: Mapped[list] = mapped_column(JSON, default=list)

    owner: Mapped[Optional["Card"]] = relationship(
        back_populates="abilities", foreign_keys=[owner_card_id]
    )


# ───────────────────────── снаряжение ─────────────────────────


class Weapon(Card):
    """Оружие — отдельный слот (манифест §4, §14)."""

    __tablename__ = "weapons"

    id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    damage_dice: Mapped[str] = mapped_column(String(8), default="1d4")
    str_requirement: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    dex_requirement: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    price: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    is_ranged: Mapped[bool] = mapped_column(Boolean, default=False)

    __mapper_args__ = {"polymorphic_identity": CardType.WEAPON.value}


class Armor(Card):
    """Броня — отдельный слот. ``phys_def_bonus`` входит в формулу физзащиты."""

    __tablename__ = "armor"

    id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    phys_def_bonus: Mapped[int] = mapped_column(Integer, default=0)
    str_requirement: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    dex_requirement: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    price: Mapped[Optional[int]] = mapped_column(Integer, default=None)

    __mapper_args__ = {"polymorphic_identity": CardType.ARMOR.value}


class Item(Card):
    """Предмет инвентаря: зелье, талисман, щит и т.д. (манифест §4).

    Предмет может **выдавать навык, пока лежит в инвентаре** (``grants_skill``):
    в отличие от навыка, такой предмет покупается и продаётся, занимает слот, и
    при продаже носитель теряет даваемую им способность (см. ``Skill``).
    """

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    price: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    is_consumable: Mapped[bool] = mapped_column(Boolean, default=False)
    # для зелий лечения — кубики хила (манифест §14)
    heal_dice: Mapped[Optional[str]] = mapped_column(String(8), default=None)
    # навык, который предмет даёт, пока находится в инвентаре
    grants_skill_id: Mapped[Optional[int]] = mapped_column(ForeignKey("skills.id"), default=None)
    grants_skill: Mapped[Optional["Skill"]] = relationship(foreign_keys=[grants_skill_id])

    __mapper_args__ = {"polymorphic_identity": CardType.ITEM.value}


class _SpellCarrierMixin:
    """Общие поля носителей одного заклинания (том и свиток)."""

    spell_name: Mapped[str] = mapped_column(String(120), default="")
    damage_dice: Mapped[Optional[str]] = mapped_column(String(8), default=None)
    # кубики splash-урона для AoE-заклинаний (None = одиночная цель)
    aoe_damage_dice: Mapped[Optional[str]] = mapped_column(String(8), default=None)
    heal_dice: Mapped[Optional[str]] = mapped_column(String(8), default=None)
    difficulty: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    attack_stat: Mapped[str] = mapped_column(String(12), default="wisdom")
    price: Mapped[Optional[int]] = mapped_column(Integer, default=None)


class SpellBook(Card, _SpellCarrierMixin):
    """Том магии: 1 заклинание, многоразово (манифест §6).

    Том покупается и носится в инвентаре, но его можно «прочитать» и получить
    постоянный навык (``teaches_skill``): купил → прочитал → выучил навык, том
    расходуется (см. ``rules.skills.learn_from_tome``).
    """

    __tablename__ = "spellbooks"

    id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    teaches_skill_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("skills.id"), default=None
    )
    teaches_skill: Mapped[Optional["Skill"]] = relationship(foreign_keys=[teaches_skill_id])

    __mapper_args__ = {"polymorphic_identity": CardType.SPELLBOOK.value}

    @property
    def is_consumable(self) -> bool:
        return False


class Scroll(Card, _SpellCarrierMixin):
    """Свиток: 1 заклинание, одноразово — исчезает после применения (§6, §9)."""

    __tablename__ = "scrolls"

    id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)

    __mapper_args__ = {"polymorphic_identity": CardType.SCROLL.value}

    @property
    def is_consumable(self) -> bool:
        return True


class Instrument(Card):
    """Инструмент (лютня, барабан) — предмет, дающий навык, пока в инвентаре.

    Инструмент покупается и продаётся и **даёт навык** (``grants_skill``), пока
    лежит в инвентаре носителя. Сам навык (например, «Песнь храбрости») —
    отдельная сущность ``Skill``; инструмент лишь предоставляет к нему доступ.
    """

    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    price: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    grants_skill_id: Mapped[Optional[int]] = mapped_column(ForeignKey("skills.id"), default=None)
    grants_skill: Mapped[Optional["Skill"]] = relationship(foreign_keys=[grants_skill_id])

    __mapper_args__ = {"polymorphic_identity": CardType.INSTRUMENT.value}


# ───────────────────────── навыки ─────────────────────────


class Skill(Card, _SpellCarrierMixin):
    """Навык — выученная постоянная способность персонажа.

    Механика **идентична** тому магии и инструменту (лютне): навык может кастовать
    заклинание (поля ``_SpellCarrierMixin``, как у тома) и/или нести способности
    ``Ability`` и пассивные ``Effect`` (как лютня — через общий ``owner_card_id``,
    т.к. навык тоже карточка).

    Отличия навыка от предмета (манифест: экономика навыков):

    * **не занимает слот инвентаря** — персонаж связан с навыками отдельной
      таблицей ``character_skills``, а не ``character_inventory``;
    * **нельзя продать и нельзя потерять** — навык остаётся с персонажем навсегда
      (не расходуется в бою, в отличие от свитка);
    * **покупается за деньги** (``price``) — например, читая том (см.
      ``SpellBook.teaches_skill``), персонаж получает навык.

    ``is_passive`` различает пассивный навык (постоянные эффекты/триггеры) и
    активный (кастует заклинание или активирует способность на своём ходу).
    """

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    is_passive: Mapped[bool] = mapped_column(Boolean, default=False)

    __mapper_args__ = {"polymorphic_identity": CardType.SKILL.value}

    @property
    def is_consumable(self) -> bool:
        return False  # навык никогда не расходуется


# ───────────────────────── персонажи и существа ─────────────────────────


character_inventory = Table(
    "character_inventory",
    Base.metadata,
    Column("character_id", ForeignKey("characters.id"), primary_key=True),
    Column("card_id", ForeignKey("cards.id"), primary_key=True),
    Column("quantity", Integer, default=1, nullable=False),
    UniqueConstraint("character_id", "card_id", name="uq_character_card"),
)

# Навыки персонажа — отдельная связь, *не* инвентарь: навык не занимает слот,
# не расходуется и не продаётся (см. ``Skill``).
character_skills = Table(
    "character_skills",
    Base.metadata,
    Column("character_id", ForeignKey("characters.id"), primary_key=True),
    Column("skill_id", ForeignKey("skills.id"), primary_key=True),
    UniqueConstraint("character_id", "skill_id", name="uq_character_skill"),
)


class Character(Card):
    """Персонаж — игрок (PC) или мастерский (NPC) (манифест §0, §2).

    При ``is_player=True`` действует пойнт-бай: база 5, +10 очков на
    распределение, минимум 1 (валидируется в ``rules.validation``). NPC
    (``is_player=False``) задаётся напрямую и не валидируется.
    """

    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    is_player: Mapped[bool] = mapped_column(Boolean, default=True)
    is_sentient: Mapped[bool] = mapped_column(Boolean, default=True)

    base_strength: Mapped[int] = mapped_column(Integer, default=5)
    base_dexterity: Mapped[int] = mapped_column(Integer, default=5)
    base_wisdom: Mapped[int] = mapped_column(Integer, default=5)
    base_charisma: Mapped[int] = mapped_column(Integer, default=5)

    # None => при загрузке считается полным от максимума
    current_hp: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    money: Mapped[int] = mapped_column(Integer, default=0)

    equipped_weapon_id: Mapped[Optional[int]] = mapped_column(ForeignKey("weapons.id"))
    equipped_armor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("armor.id"))

    equipped_weapon: Mapped[Optional["Weapon"]] = relationship(
        foreign_keys=[equipped_weapon_id]
    )
    equipped_armor: Mapped[Optional["Armor"]] = relationship(
        foreign_keys=[equipped_armor_id]
    )
    inventory: Mapped[list["Card"]] = relationship(
        secondary=character_inventory,
        primaryjoin="Character.id == character_inventory.c.character_id",
        secondaryjoin="Card.id == character_inventory.c.card_id",
    )
    # выученные навыки — постоянные, вне инвентаря (см. Skill)
    skills: Mapped[list["Skill"]] = relationship(
        secondary=character_skills,
        primaryjoin="Character.id == character_skills.c.character_id",
        secondaryjoin="Skill.id == character_skills.c.skill_id",
    )

    __mapper_args__ = {
        "polymorphic_identity": CardType.CHARACTER.value,
        "inherit_condition": id == Card.id,
    }


class Creature(Card):
    """Существо/монстр (манифест §13). Защиты задаются напрямую, не через DEX."""

    __tablename__ = "creatures"

    id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    is_sentient: Mapped[bool] = mapped_column(Boolean, default=False)

    hp: Mapped[int] = mapped_column(Integer, default=1)
    current_hp: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    dexterity: Mapped[int] = mapped_column(Integer, default=0)  # для инициативы
    phys_defense: Mapped[int] = mapped_column(Integer, default=0)
    mag_defense: Mapped[int] = mapped_column(Integer, default=0)
    mental_defense: Mapped[int] = mapped_column(Integer, default=0)
    phys_damage_dice: Mapped[str] = mapped_column(String(8), default="1d8")

    # для групповых механик (устрашение/переговоры, §12)
    strength: Mapped[int] = mapped_column(Integer, default=0)
    charisma: Mapped[int] = mapped_column(Integer, default=0)
    wisdom: Mapped[int] = mapped_column(Integer, default=0)

    __mapper_args__ = {"polymorphic_identity": CardType.CREATURE.value}


# ───────────────────────── лор-записи мира (приключение/RAG) ─────────────────────────


class LoreEntry(Card):
    """Лор-запись о мире Гроханика: локация, фракция, факт истории и т.п.

    Это тоже карточка (общий ``name``/``description``), что переиспользует админку,
    сериализацию и семантический поиск. Текст факта — в ``description``. ``category``
    группирует записи (локации, фракции, история, кастом) и используется в RAG, чтобы
    ИИ-ГМ опирался на существующий лор, а не выдумывал мир.

    ``lore_id`` — исходный идентификатор из базы фактов (H-001, R-013, ...).
    ``when_to_apply`` — подсказка ГМу: в каких сценах применять этот факт.
    ``notes`` — нюансы: распространённые ошибки, важные уточнения.
    Все три поля включаются в текст для эмбеддинга — расширяют семантику поиска.
    """

    __tablename__ = "lore_entries"

    id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    category: Mapped[str] = mapped_column(String(24), default="custom")
    lore_id: Mapped[Optional[str]] = mapped_column(String(8), default=None)
    when_to_apply: Mapped[str] = mapped_column(String, default="")
    notes: Mapped[str] = mapped_column(String, default="")

    __mapper_args__ = {"polymorphic_identity": CardType.LORE.value}


# ───────────────────────── эмбеддинги (вектор-поиск) ─────────────────────────


class Embedding(Base):
    """Векторное представление сущности для семантического поиска (RAG).

    Универсальная таблица: ``entity_type`` ∈ {``card``, ``lore``, ``turn``},
    ``entity_id`` — id карточки/лор-записи/сообщения приключения. ``vector`` хранит
    L2-нормированный ``float32``-вектор как BLOB; ``text_hash`` позволяет понять,
    что исходный текст изменился и вектор нужно пересчитать.
    """

    __tablename__ = "embeddings"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", name="uq_embedding_entity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(12), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    model: Mapped[str] = mapped_column(String(120))
    dim: Mapped[int] = mapped_column(Integer)
    vector: Mapped[bytes] = mapped_column(LargeBinary)
    text_hash: Mapped[str] = mapped_column(String(64))


# ───────────────────────── настройки приложения (конфиг LLM) ─────────────────────────


class AppSetting(Base):
    """Пара ключ→JSON для настроек, редактируемых через фронтенд (конфиг LLM и пр.)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


# ───────────────────────── сессии приключения ─────────────────────────


adventure_party = Table(
    "adventure_party",
    Base.metadata,
    Column("session_id", ForeignKey("adventure_sessions.id"), primary_key=True),
    Column("character_id", ForeignKey("characters.id"), primary_key=True),
)


class AdventureSession(Base):
    """Сессия текстового приключения: сетап, партия, статус и состояние контекста."""

    __tablename__ = "adventure_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(String, default="")  # свободный сетап
    adventure_type: Mapped[str] = mapped_column(String(80), default="custom")
    goal: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String(12), default="setup")  # setup|active|ended
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # локация — свободный текст (имя + описание), не привязана к карточкам каталога:
    # её решает интент-анализатор (детерминированно, temperature=0), а не RAG-поиск
    current_location_name: Mapped[str] = mapped_column(String(200), default="")
    current_location_description: Mapped[str] = mapped_column(String, default="")
    system_prompt: Mapped[str] = mapped_column(String, default="")  # снимок промта ГМ
    # бегущая сводка кампании (компактинг) + докуда уже свёрнуто
    running_summary: Mapped[str] = mapped_column(String, default="")
    summarized_through_message_id: Mapped[Optional[int]] = mapped_column(Integer, default=None)

    party: Mapped[list["Character"]] = relationship(
        secondary=adventure_party,
        primaryjoin="AdventureSession.id == adventure_party.c.session_id",
        secondaryjoin="Character.id == adventure_party.c.character_id",
    )
    messages: Mapped[list["AdventureMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AdventureMessage.id",
    )
    pins: Mapped[list["ScenePin"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class AdventureMessage(Base):
    """Сообщение в приключении: реплика ГМ, игрока или системное событие."""

    __tablename__ = "adventure_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("adventure_sessions.id"))
    role: Mapped[str] = mapped_column(String(8))  # gm | player | system
    speaker_character_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("characters.id"), default=None
    )
    content: Mapped[str] = mapped_column(String, default="")
    intent_json: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["AdventureSession"] = relationship(back_populates="messages")
    speaker: Mapped[Optional["Character"]] = relationship(foreign_keys=[speaker_character_id])


class ScenePin(Base):
    """Карточка, закреплённая в текущей сцене (для UI и промта ГМ).

    При уходе из локации неигровые акторы деактивируются (``active=False``), а не
    удаляются — это сохраняет историю сцены и позволяет вернуться.
    """

    __tablename__ = "scene_pins"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("adventure_sessions.id"))
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"))
    kind: Mapped[str] = mapped_column(String(12))  # npc
    count: Mapped[int] = mapped_column(Integer, default=1)  # сколько таких NPC в кадре
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    session: Mapped["AdventureSession"] = relationship(back_populates="pins")
    card: Mapped["Card"] = relationship(foreign_keys=[card_id])
