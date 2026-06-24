"""Боевой участник — рантайм-снимок карточки (Character или Creature).

Карточка в БД — шаблон. Бой меняет не её, а ``Combatant``: текущие HP, активные
эффекты, флаги «сбежал/погиб». Снимок снимается один раз при входе в бой, дальше
БД не нужна.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional

from ..enums import ActivationSource, EffectTarget, HPState, Stat
from ..db.models import Character, Creature
from ..rules import attributes as attr
from ..rules.effects import RuntimeEffect, add_effect

# уникальные id участников боя в пределах процесса (призванные существа делят
# card_id, поэтому для адресации цели нужен отдельный стабильный идентификатор)
_uid_counter = itertools.count(1)


@dataclass
class AbilitySpec:
    """Снимок способности карточки для движка способностей."""

    name: str
    trigger: str
    actions: list
    chance: Optional[float] = None
    once_per_combat: bool = False
    condition: Optional[dict] = None
    source_name: str = ""
    used: bool = False


@dataclass
class _WeaponSnap:
    damage_dice: str
    is_ranged: bool


@dataclass
class _ItemSnap:
    name: str
    card_id: int
    card_type: str
    is_consumable: bool
    heal_dice: Optional[str]
    effects: list[RuntimeEffect] = field(default_factory=list)
    quantity: int = 1
    # для томов и свитков — данные заклинания
    spell_name: Optional[str] = None
    spell_damage_dice: Optional[str] = None
    spell_difficulty: Optional[int] = None

    @property
    def is_potion(self) -> bool:
        return self.heal_dice is not None

    @property
    def is_spell_carrier(self) -> bool:
        return self.spell_damage_dice is not None and self.spell_difficulty is not None


class Combatant:
    """Активный участник боя."""

    def __init__(self, card, side: str) -> None:
        self.uid: int = next(_uid_counter)
        self.card_id: int = card.id
        self.name: str = card.name
        self.side: str = side
        self.kind: str = card.card_type
        self.is_sentient: bool = bool(getattr(card, "is_sentient", False))

        self.temporary_effects: list[RuntimeEffect] = []
        self.active_effects: list[RuntimeEffect] = []
        self.abilities: list[AbilitySpec] = []

        # снимки снаряжения / прямых параметров
        self.weapon: Optional[_WeaponSnap] = None
        self.armor_phys_def_bonus: int = 0
        self.inventory: list[_ItemSnap] = []
        # навыки: кастующие источники (как тома) и постоянные эффекты — вне инвентаря
        self.skill_carriers: list[_ItemSnap] = []
        self._skill_effects: list[RuntimeEffect] = []
        self._weapon_effects: list[RuntimeEffect] = []
        self._armor_effects: list[RuntimeEffect] = []

        # базовые характеристики (для существа берём из его полей)
        self.base_strength = self.base_dexterity = 0
        self.base_wisdom = self.base_charisma = 0
        # прямые защиты/урон существа
        self._creature_base_hp = 0
        self._direct_phys_def = 0
        self._direct_mag_def = 0
        self._direct_mental_def = 0
        self._direct_damage_dice = "1d8"

        # статусы
        self.escaped = False
        self.dead = False

        if isinstance(card, Character):
            self._init_character(card)
        elif isinstance(card, Creature):
            self._init_creature(card)
        else:  # pragma: no cover - в бой попадают только персонажи и существа
            raise TypeError(f"Combatant поддерживает только Character/Creature, не {card!r}")

        self._gather_abilities(card)
        self.recompute_active_effects()

        starting = card.current_hp
        self.current_hp = self.max_hp if starting is None else starting

    # ───────── инициализация из карточки ─────────

    def _init_character(self, card: Character) -> None:
        self.base_strength = card.base_strength
        self.base_dexterity = card.base_dexterity
        self.base_wisdom = card.base_wisdom
        self.base_charisma = card.base_charisma

        if card.equipped_weapon is not None:
            w = card.equipped_weapon
            self.weapon = _WeaponSnap(damage_dice=w.damage_dice, is_ranged=w.is_ranged)
            self._weapon_effects = [RuntimeEffect.from_orm(e) for e in w.effects]
            self._gather_abilities(w)

        if card.equipped_armor is not None:
            a = card.equipped_armor
            self.armor_phys_def_bonus = a.phys_def_bonus
            self._armor_effects = [RuntimeEffect.from_orm(e) for e in a.effects]
            self._gather_abilities(a)

        for item_card in card.inventory:
            self.inventory.append(
                _ItemSnap(
                    name=item_card.name,
                    card_id=item_card.id,
                    card_type=item_card.card_type,
                    is_consumable=bool(getattr(item_card, "is_consumable", False)),
                    heal_dice=getattr(item_card, "heal_dice", None),
                    effects=[RuntimeEffect.from_orm(e) for e in item_card.effects],
                    spell_name=getattr(item_card, "spell_name", None),
                    spell_damage_dice=getattr(item_card, "damage_dice", None),
                    spell_difficulty=getattr(item_card, "difficulty", None),
                )
            )
            self._gather_abilities(item_card)
            # предмет может давать навык, пока лежит в инвентаре (лютня → «Песнь храбрости»)
            granted = getattr(item_card, "grants_skill", None)
            if granted is not None:
                self._snapshot_skill(granted)

        # постоянные навыки — куплены напрямую, вне инвентаря (механика как у тома/лютни)
        for skill_card in getattr(card, "skills", []):
            self._snapshot_skill(skill_card)

    def _snapshot_skill(self, skill_card) -> None:
        """Снять способности навыка (постоянного или даваемого предметом).

        Внутри боя постоянный навык и навык от предмета ведут себя одинаково;
        разница (можно ли продать) важна лишь вне боя.
        """
        self._gather_abilities(skill_card)  # активные/триггерные способности навыка
        # эффекты навыка активны всегда, пока навык доступен
        self._skill_effects.extend(RuntimeEffect.from_orm(e) for e in skill_card.effects)
        # навык-заклинание (как том): кастуемый источник, который не расходуется
        if getattr(skill_card, "damage_dice", None) and getattr(skill_card, "difficulty", None):
            self.skill_carriers.append(
                _ItemSnap(
                    name=skill_card.name,
                    card_id=skill_card.id,
                    card_type=skill_card.card_type,
                    is_consumable=False,
                    heal_dice=getattr(skill_card, "heal_dice", None),
                    effects=[],
                    spell_name=getattr(skill_card, "spell_name", None),
                    spell_damage_dice=getattr(skill_card, "damage_dice", None),
                    spell_difficulty=getattr(skill_card, "difficulty", None),
                )
            )

    def _init_creature(self, card: Creature) -> None:
        self.base_strength = card.strength
        self.base_dexterity = card.dexterity
        self.base_wisdom = card.wisdom
        self.base_charisma = card.charisma
        self._creature_base_hp = card.hp
        self._direct_phys_def = card.phys_defense
        self._direct_mag_def = card.mag_defense
        self._direct_mental_def = card.mental_defense
        self._direct_damage_dice = card.phys_damage_dice

    def _gather_abilities(self, card) -> None:
        for ab in getattr(card, "abilities", []):
            self.abilities.append(
                AbilitySpec(
                    name=ab.name,
                    trigger=ab.trigger,
                    actions=list(ab.actions or []),
                    chance=ab.chance,
                    once_per_combat=ab.once_per_combat,
                    condition=ab.condition,
                    source_name=card.name,
                )
            )

    # ───────── активные эффекты ─────────

    def recompute_active_effects(self) -> None:
        effects: list[RuntimeEffect] = list(self._weapon_effects) + list(self._armor_effects)
        weapon_ranged = self.weapon is not None and self.weapon.is_ranged
        for item in self.inventory:
            for e in item.effects:
                if e.activation_source == ActivationSource.IN_INVENTORY.value:
                    effects.append(e)
                elif (
                    e.activation_source == ActivationSource.IN_INVENTORY_RANGED.value
                    and weapon_ranged
                ):
                    effects.append(e)
        # эффекты навыков активны всегда (не зависят от activation_source)
        effects.extend(self._skill_effects)
        effects.extend(self.temporary_effects)
        self.active_effects = effects

    @property
    def spell_carriers(self) -> list["_ItemSnap"]:
        """Все источники заклинаний: тома/свитки в инвентаре + навыки-заклинания."""
        return [it for it in self.inventory if it.is_spell_carrier] + list(self.skill_carriers)

    def add_temporary_effect(self, effect: RuntimeEffect) -> None:
        add_effect(self.temporary_effects, effect)
        self.recompute_active_effects()

    # ───────── эффективные характеристики ─────────

    @property
    def str_eff(self) -> int:
        return attr.effective_stat(self.base_strength, self.active_effects, Stat.STRENGTH)

    @property
    def dex_eff(self) -> int:
        return attr.effective_stat(self.base_dexterity, self.active_effects, Stat.DEXTERITY)

    @property
    def wis_eff(self) -> int:
        return attr.effective_stat(self.base_wisdom, self.active_effects, Stat.WISDOM)

    @property
    def cha_eff(self) -> int:
        return attr.effective_stat(self.base_charisma, self.active_effects, Stat.CHARISMA)

    # ───────── вычисляемые атрибуты ─────────

    @property
    def max_hp(self) -> int:
        if self.kind == "creature":
            # для существа базовый hp хранится в _direct... используем поле hp через snapshot
            return attr.creature_max_hp(self._creature_base_hp, self.active_effects)
        return attr.character_max_hp(self.str_eff, self.active_effects)

    @property
    def phys_defense(self) -> int:
        if self.kind == "creature":
            return attr.creature_defense(
                self._direct_phys_def, self.active_effects, EffectTarget.PHYS_DEFENSE
            )
        return attr.character_phys_defense(
            self.dex_eff, self.armor_phys_def_bonus, self.active_effects
        )

    @property
    def mag_defense(self) -> int:
        if self.kind == "creature":
            return attr.creature_defense(
                self._direct_mag_def, self.active_effects, EffectTarget.MAG_DEFENSE
            )
        return attr.character_mag_defense(self.wis_eff, self.active_effects)

    @property
    def mental_defense(self) -> int:
        if self.kind == "creature":
            return attr.creature_defense(
                self._direct_mental_def, self.active_effects, EffectTarget.MENTAL_DEFENSE
            )
        return attr.character_mental_defense(self.cha_eff, self.active_effects)

    @property
    def phys_attack_bonus(self) -> int:
        return attr.attack_bonus(self.dex_eff)

    @property
    def mag_attack_bonus(self) -> int:
        return attr.attack_bonus(self.wis_eff)

    @property
    def mental_attack_bonus(self) -> int:
        return attr.attack_bonus(self.cha_eff)

    @property
    def phys_damage_dice(self) -> str:
        if self.kind == "creature":
            return self._direct_damage_dice
        return self.weapon.damage_dice if self.weapon is not None else "1d4"

    @property
    def phys_damage_bonus(self) -> int:
        return attr.damage_bonus(self.str_eff, self.active_effects)

    # ───────── состояние HP (§11) ─────────

    @property
    def state(self) -> HPState:
        return HPState.DYING if self.current_hp <= 0 else HPState.ACTIVE

    @property
    def is_dying(self) -> bool:
        return self.state is HPState.DYING

    @property
    def in_combat(self) -> bool:
        """Участвует ли в бою (не сбежал и не погиб окончательно)."""
        return not self.escaped and not self.dead

    @property
    def has_bastion(self) -> bool:
        """Активна ли у участника способность «Бастион» (taunt-защита строя).

        Маркер несёт всегда-активный эффект навыка (см. enums.EffectTarget.BASTION),
        поэтому свойство истинно, пока навык доступен (предмет в инвентаре и т.п.).
        Учитывать «живость» носителя должен вызывающий код (мёртвый не держит строй).
        """
        return any(e.target == EffectTarget.BASTION.value for e in self.active_effects)

    @property
    def can_act(self) -> bool:
        """Может ли действовать: жив, в бою и не Dying."""
        return self.in_combat and not self.is_dying

    def take_damage(self, amount: int) -> int:
        amount = max(0, amount)
        self.current_hp = max(0, self.current_hp - amount)
        return amount

    def heal(self, amount: int) -> int:
        """Вылечить, не превышая максимум. Возвращает фактически восстановленное."""
        if amount <= 0:
            return 0
        before = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + amount)
        return self.current_hp - before

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Combatant {self.name!r} hp={self.current_hp}/{self.max_hp} side={self.side}>"
