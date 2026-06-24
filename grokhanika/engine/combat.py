"""Боевой движок «Гроханики» (манифест §7–§12).

``Combat`` хранит участников и состояние боя, методы реализуют правила: бросок
инициативы, физ./маг./мент. атаки, групповые механики (побег, устрашение,
переговоры), мораль, лечение, конец раунда. Весь рандом — через ``self.rng``,
поэтому бой воспроизводим.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Iterable, Optional

from ..dice import Dice, is_crit, is_fumble, roll_d20
from ..enums import (
    AbilityTrigger,
    EffectTarget,
    EffectTargetType,
    SourceType,
)
from ..rules.effects import RuntimeEffect, roll_modifier, tick_round
from .abilities import AbilityContext, fire_abilities
from .combatant import Combatant

FLEE_THRESHOLD = 10
MORALE_MODIFIER = -2


# ───────────────────────── результаты ─────────────────────────


@dataclass
class AttackResult:
    attacker: str
    defender: str
    natural: int
    total: int
    threshold: int
    hit: bool
    crit: bool = False
    fumble: bool = False
    damage: int = 0
    killed: bool = False


@dataclass
class SpellResult:
    caster: str
    target: str
    activated: bool
    activation_total: int
    difficulty: int
    saved: Optional[bool] = None
    damage: int = 0
    debuff_applied: bool = False
    killed: bool = False


@dataclass
class MentalResult:
    attacker: str
    target: str
    attack_total: int
    defense_total: int
    success: bool


@dataclass
class MechanicResult:
    name: str
    available: bool
    success: bool = False
    attacker_total: int = 0
    defender_total: int = 0
    detail: str = ""


# ───────────────────────── бой ─────────────────────────


class Combat:
    def __init__(
        self,
        combatants: Iterable[Combatant],
        *,
        rng: Optional[random.Random] = None,
        session=None,
    ) -> None:
        self.combatants: list[Combatant] = list(combatants)
        self.rng = rng or random.Random()
        self.session = session
        self.round = 0
        self.log: list[str] = []
        # единственная спец. механика за бой: устрашение ИЛИ переговоры (§12)
        self.special_mechanic_used = False
        self.finished_by_negotiation = False

    # ───────── вспомогательное ─────────

    def add_combatant(self, combatant: Combatant) -> None:
        self.combatants.append(combatant)

    def get(self, uid: int) -> Optional[Combatant]:
        """Найти участника по его уникальному ``uid``."""
        return next((c for c in self.combatants if c.uid == uid), None)

    def sides(self) -> set[str]:
        return {c.side for c in self.combatants}

    def members(self, side: str, *, alive_only: bool = True) -> list[Combatant]:
        out = []
        for c in self.combatants:
            if c.side != side:
                continue
            if alive_only and not c.in_combat:
                continue
            out.append(c)
        return out

    def opponents_of(self, combatant: Combatant) -> list[Combatant]:
        return [c for c in self.combatants if c.side != combatant.side and c.in_combat]

    def _ctx(self, actor: Combatant, target: Optional[Combatant] = None) -> AbilityContext:
        return AbilityContext(actor=actor, rng=self.rng, combat=self, target=target, log=self.log)

    def is_over(self) -> bool:
        if self.finished_by_negotiation:
            return True
        active_sides = {c.side for c in self.combatants if c.in_combat and not c.is_dying}
        return len(active_sides) <= 1

    def winner(self) -> Optional[str]:
        sides = {c.side for c in self.combatants if c.in_combat and not c.is_dying}
        return next(iter(sides)) if len(sides) == 1 else None

    # ───────── инициатива (§7) ─────────

    def roll_initiative(self) -> list[Combatant]:
        # сортировка по DEX_eff убыв.; тай-брейк d20
        decorated = [(c.dex_eff, roll_d20(self.rng), c) for c in self.combatants if c.in_combat]
        decorated.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [c for _, _, c in decorated]

    # ───────── физическая атака (§8) ─────────

    def physical_attack(self, attacker: Combatant, defender: Combatant) -> AttackResult:
        natural = roll_d20(self.rng)
        bonus = attacker.phys_attack_bonus + roll_modifier(attacker.active_effects, attack=True)
        total = natural + bonus
        threshold = defender.phys_defense
        crit = is_crit(natural)
        fumble = is_fumble(natural)
        hit = crit or (not fumble and total >= threshold)

        result = AttackResult(
            attacker=attacker.name,
            defender=defender.name,
            natural=natural,
            total=total,
            threshold=threshold,
            hit=hit,
            crit=crit,
            fumble=fumble,
        )
        if hit:
            dice = Dice.parse(attacker.phys_damage_dice)
            result.damage = dice.roll(self.rng, crit=crit) + attacker.phys_damage_bonus
            defender.take_damage(result.damage)
            self.log.append(
                f"{attacker.name} бьёт {defender.name}: {natural}+{bonus} vs {threshold} → "
                f"{'КРИТ ' if crit else ''}{result.damage} урона"
            )
            self._fire_hit(attacker, defender, result)
        else:
            self.log.append(
                f"{attacker.name} промахивается по {defender.name}: {natural}+{bonus} vs {threshold}"
            )
        return result

    # ───────── магическая атака (§9) ─────────

    def magical_attack(
        self,
        caster: Combatant,
        defender: Combatant,
        *,
        damage_dice: str,
        difficulty: int,
        debuff: Optional[RuntimeEffect] = None,
    ) -> SpellResult:
        # шаг 1 — активация
        natural = roll_d20(self.rng)
        bonus = caster.mag_attack_bonus + roll_modifier(caster.active_effects, attack=True)
        activation_total = natural + bonus
        crit = is_crit(natural)
        activated = crit or (not is_fumble(natural) and activation_total >= difficulty)

        result = SpellResult(
            caster=caster.name,
            target=defender.name,
            activated=activated,
            activation_total=activation_total,
            difficulty=difficulty,
        )
        if not activated:
            self.log.append(
                f"{caster.name} проваливает заклинание: {activation_total} < сл.{difficulty}"
            )
            return result

        # шаг 2 — спасбросок цели
        save_natural = roll_d20(self.rng)
        save_total = (
            save_natural
            + defender.mag_defense
            + roll_modifier(defender.active_effects, attack=False)
        )
        saved = save_total >= activation_total
        result.saved = saved

        damage = Dice.parse(damage_dice).roll(self.rng, crit=crit)
        if saved:
            damage = math.ceil(damage / 2)  # спас успешен: половина, дебафф не вешается
        else:
            if debuff is not None:
                defender.add_temporary_effect(debuff)
                result.debuff_applied = True
        result.damage = damage
        defender.take_damage(damage)
        self.log.append(
            f"{caster.name} кастует в {defender.name}: спас {save_total} vs {activation_total} → "
            f"{'половина ' if saved else ''}{damage} урона"
        )
        self._fire_hit(caster, defender, result)
        return result

    def cast_from_carrier(
        self, caster: Combatant, defender: Combatant, carrier_card_id: int
    ) -> Optional[SpellResult]:
        """Скастовать заклинание из тома/свитка в инвентаре.

        Переиспользует ``magical_attack``. Свиток (``is_consumable``) расходуется
        и исчезает из инвентаря после применения (§9).
        """
        carrier = next(
            (
                it
                for it in caster.spell_carriers
                if it.card_id == carrier_card_id and it.is_spell_carrier
            ),
            None,
        )
        if carrier is None:
            self.log.append(f"{caster.name}: нет такого носителя заклинания")
            return None

        result = self.magical_attack(
            caster,
            defender,
            damage_dice=carrier.spell_damage_dice,
            difficulty=carrier.spell_difficulty,
        )
        # навык-заклинание не расходуется; расходуется лишь одноразовый предмет (свиток)
        if carrier.is_consumable:
            carrier.quantity -= 1
            if carrier.quantity <= 0 and carrier in caster.inventory:
                caster.inventory.remove(carrier)
            caster.recompute_active_effects()
            self.log.append(f"{caster.name}: свиток «{carrier.name}» израсходован")
        return result

    # ───────── ментальная атака (§10) ─────────

    def mental_attack(
        self, attacker: Combatant, target: Combatant, *, effect: Optional[RuntimeEffect] = None
    ) -> MentalResult:
        atk_natural = roll_d20(self.rng)
        attack_total = (
            atk_natural
            + attacker.mental_attack_bonus
            + roll_modifier(attacker.active_effects, attack=True)
        )
        def_natural = roll_d20(self.rng)
        defense_total = (
            def_natural
            + target.mental_defense
            + roll_modifier(target.active_effects, attack=False)
        )
        success = attack_total > defense_total
        if success and effect is not None:
            target.add_temporary_effect(effect)
        self.log.append(
            f"{attacker.name} мент.атака на {target.name}: {attack_total} vs {defense_total} → "
            f"{'успех' if success else 'провал'}"
        )
        return MentalResult(
            attacker=attacker.name,
            target=target.name,
            attack_total=attack_total,
            defense_total=defense_total,
            success=success,
        )

    # ───────── лечение / зелья (§11) ─────────

    def use_potion(self, user: Combatant, item_name: Optional[str] = None) -> int:
        """Применить зелье из инвентаря (тратит ход). Работает на Dying → Revived."""
        potion = None
        for it in user.inventory:
            if it.heal_dice and (item_name is None or it.name == item_name):
                potion = it
                break
        if potion is None:
            self.log.append(f"{user.name}: нет зелья лечения")
            return 0
        healed = user.heal(Dice.parse(potion.heal_dice).roll(self.rng))
        if potion.is_consumable:
            potion.quantity -= 1
            if potion.quantity <= 0:
                user.inventory.remove(potion)
        self.log.append(f"{user.name} пьёт {potion.name}: +{healed} HP (теперь {user.current_hp})")
        return healed

    # ───────── групповые механики (§12) ─────────

    def attempt_flee(self, combatant: Combatant) -> bool:
        """Индивидуальный бросок побега. Успех → вышел из боя, провал → гибель."""
        natural = roll_d20(self.rng)
        total = natural + combatant.dex_eff
        survived = total >= FLEE_THRESHOLD
        if survived:
            combatant.escaped = True
            self.log.append(f"{combatant.name} сбегает ({total} ≥ {FLEE_THRESHOLD})")
        else:
            combatant.dead = True
            self.log.append(f"{combatant.name} гибнет при побеге ({total} < {FLEE_THRESHOLD})")
        return survived

    def _sum_str(self, side: str) -> int:
        return sum(c.str_eff for c in self.members(side))

    def _most_charismatic(self, side: str) -> Optional[Combatant]:
        members = self.members(side)
        return max(members, key=lambda c: c.cha_eff) if members else None

    def intimidate(self, initiator: Combatant, enemy_side: str) -> MechanicResult:
        """Устрашение (§12)."""
        result = MechanicResult(name="intimidate", available=False)
        enemies = self.members(enemy_side)
        if self.special_mechanic_used:
            result.detail = "спец. механика уже применялась в этом бою"
            return result
        if not any(c.is_sentient for c in enemies):
            result.detail = "во вражеской группе нет разумного существа"
            return result
        if self._sum_str(initiator.side) <= self._sum_str(enemy_side):
            result.detail = "SUM(STR союзников) не больше SUM(STR врагов)"
            return result

        result.available = True
        self.special_mechanic_used = True
        champion = self._most_charismatic(enemy_side)
        atk = roll_d20(self.rng) + initiator.cha_eff // 2
        dfn = roll_d20(self.rng) + (champion.cha_eff // 2 if champion else 0)
        result.attacker_total, result.defender_total = atk, dfn
        result.success = atk > dfn
        if result.success:
            self.log.append(f"{initiator.name}: устрашение удалось — враги бегут")
            for enemy in self.members(enemy_side):
                self.attempt_flee(enemy)
        else:
            self.log.append(f"{initiator.name}: устрашение провалено — мораль падает")
            self.apply_morale_debuff(initiator.side)
        return result

    def negotiate(self, initiator: Combatant, enemy_side: str) -> MechanicResult:
        """Переговоры (§12)."""
        result = MechanicResult(name="negotiate", available=False)
        enemies = self.members(enemy_side)
        if self.special_mechanic_used:
            result.detail = "спец. механика уже применялась в этом бою"
            return result
        if not any(c.is_sentient for c in enemies):
            result.detail = "во вражеской группе нет разумного существа"
            return result

        result.available = True
        self.special_mechanic_used = True
        champion = self._most_charismatic(enemy_side)
        atk = roll_d20(self.rng) + initiator.cha_eff // 2 + initiator.wis_eff // 2
        dfn = roll_d20(self.rng)
        if champion:
            dfn += champion.cha_eff // 2 + champion.wis_eff // 2
        result.attacker_total, result.defender_total = atk, dfn
        result.success = atk > dfn
        if result.success:
            self.finished_by_negotiation = True
            self.log.append(f"{initiator.name}: переговоры удались — бой переходит в диалог")
        else:
            self.log.append(f"{initiator.name}: переговоры провалены — мораль падает")
            self.apply_morale_debuff(initiator.side)
        return result

    def apply_morale_debuff(self, side: str) -> None:
        """Дебафф морали: -2 ко всем броскам атаки до конца боя, не стэкается (§12)."""
        for member in self.members(side):
            member.add_temporary_effect(
                RuntimeEffect(
                    target_type=EffectTargetType.ATTR.value,
                    target=EffectTarget.ALL_ATTACK_ROLLS.value,
                    modifier=MORALE_MODIFIER,
                    duration=0,  # до конца боя
                    source_type=SourceType.MORALE.value,
                    source_id=None,
                    is_stackable=False,
                    description="Дебафф морали",
                )
            )

    # ───────── конец раунда ─────────

    def end_round(self) -> None:
        """Декремент длительностей эффектов у всех участников (§5)."""
        self.round += 1
        for c in self.combatants:
            tick_round(c.temporary_effects)
            c.recompute_active_effects()

    # ───────── способности ─────────

    def _fire_hit(self, attacker: Combatant, defender: Combatant, result) -> None:
        ctx = self._ctx(attacker, defender)
        fire_abilities(attacker, AbilityTrigger.ON_HIT, ctx, target=defender)
        if defender.is_dying or defender.dead:
            result.killed = True
            fire_abilities(attacker, AbilityTrigger.ON_KILL, ctx, target=defender)

    def fire_combat_start(self) -> None:
        for c in list(self.combatants):
            fire_abilities(c, AbilityTrigger.ON_COMBAT_START, self._ctx(c))

    def trigger(self, actor: Combatant, trigger, target: Optional[Combatant] = None) -> list[str]:
        """Запустить способности участника по произвольному триггеру (напр. начало хода)."""
        return fire_abilities(actor, trigger, self._ctx(actor, target), target=target)

    def activate_ability(
        self, actor: Combatant, ability_name: Optional[str] = None, target: Optional[Combatant] = None
    ) -> list[str]:
        """Вручную активировать ACTIVE-способность участника (тратит ход)."""
        return fire_abilities(
            actor,
            AbilityTrigger.ACTIVE,
            self._ctx(actor, target),
            target=target,
            only_name=ability_name,
        )
