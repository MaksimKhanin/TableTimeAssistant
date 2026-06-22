import random
from typing import Optional

# ── Character build rules ──────────────────────────────────────────────────────
STAT_KEYS = ["strength", "dexterity", "wisdom", "charisma"]
STAT_MIN = 1
STAT_MAX = 20
# Default 5 each = 20; player gets 10 extra points to distribute → max sum 30
POINT_BUDGET = 30
STAT_DEFAULT = 5


def derive_stats(strength: int, dexterity: int, wisdom: int, charisma: int) -> dict:
    """Compute all derived combat stats from the four base attributes."""
    return {
        "max_hp": 10 + strength // 2,
        "phys_defense": dexterity // 2,
        "mag_defense": wisdom // 2,
        "mental_defense": 5 + charisma // 2,
        "phys_attack_bonus": dexterity // 2,
        "mag_attack_bonus": wisdom // 2,
        "mental_attack_bonus": charisma // 2,
        # damage_dice modifier is applied at roll time as strength // 2
    }


def roll(sides: int, count: int = 1) -> list[int]:
    return [random.randint(1, sides) for _ in range(count)]


def roll_total(sides: int, count: int = 1, modifier: int = 0) -> int:
    return sum(roll(sides, count)) + modifier


def _d20(die: Optional[int] = None) -> int:
    if die is not None:
        return max(1, min(20, int(die)))
    return roll(20)[0]


def roll_initiative(dexterity: int, die: Optional[int] = None) -> dict:
    d = _d20(die)
    return {"die": d, "bonus": dexterity, "total": d + dexterity}


def roll_phys_attack(phys_attack_bonus: int = 0, die: Optional[int] = None) -> dict:
    d = _d20(die)
    total = d + phys_attack_bonus
    return {"die": d, "bonus": phys_attack_bonus, "total": total, "critical": d == 20, "fumble": d == 1}


# Keep old name as alias for backward compat
def roll_attack(attack_bonus: int = 0, die: Optional[int] = None) -> dict:
    return roll_phys_attack(attack_bonus, die)


def roll_mag_attack(mag_attack_bonus: int = 0, die: Optional[int] = None) -> dict:
    d = _d20(die)
    total = d + mag_attack_bonus
    return {"die": d, "bonus": mag_attack_bonus, "total": total, "critical": d == 20, "fumble": d == 1}


def roll_mental_attack(mental_attack_bonus: int = 0, die: Optional[int] = None) -> dict:
    d = _d20(die)
    total = d + mental_attack_bonus
    return {"die": d, "bonus": mental_attack_bonus, "total": total, "critical": d == 20, "fumble": d == 1}


def roll_ability_check(stat: int, dc: Optional[int] = None, die: Optional[int] = None) -> dict:
    mod = stat // 2
    d = _d20(die)
    total = d + mod
    out = {"die": d, "modifier": mod, "total": total, "critical": d == 20, "fumble": d == 1}
    if dc is not None:
        out["dc"] = dc
        out["success"] = total >= dc
    return out


def roll_saving_throw(defense: int, dc: int, die: Optional[int] = None) -> dict:
    """Saving throw uses the defense value directly as modifier."""
    d = _d20(die)
    total = d + defense
    return {"die": d, "modifier": defense, "total": total, "dc": dc, "success": total >= dc}


def roll_damage(dice_notation: str, modifier: int = 0, manual_total: Optional[int] = None) -> dict:
    if manual_total is not None:
        t = max(0, int(manual_total))
        return {"rolls": [t], "extra": 0, "modifier": 0, "total": t, "manual": True}

    notation = dice_notation.strip()
    extra = 0
    if "+" in notation:
        parts = notation.split("+")
        notation = parts[0].strip()
        extra = int(parts[1].strip())
    elif "-" in notation:
        parts = notation.split("-")
        notation = parts[0].strip()
        extra = -int(parts[1].strip())

    if "d" in notation:
        count_str, sides_str = notation.split("d")
        count = int(count_str) if count_str else 1
        sides = int(sides_str)
    else:
        count, sides = 1, 4

    rolls = roll(sides, count)
    total = sum(rolls) + extra + modifier
    return {"rolls": rolls, "extra": extra, "modifier": modifier, "total": max(0, total)}


COMBAT_ACTIONS = ["Атака", "Рывок", "Отступление", "Уклонение", "Помощь", "Скрытность", "Заклинание", "Ментальная атака"]


def format_roll_result(result: dict, context: str = "") -> str:
    parts = []
    if context:
        parts.append(f"**{context}**")
    if "die" in result:
        parts.append(f"🎲 d20={result['die']}")
        if result.get("bonus"):
            parts.append(f"+ {result['bonus']}")
        parts.append(f"= **{result['total']}**")
        if result.get("critical"):
            parts.append("🌟 КРИТИЧЕСКИЙ УДАР!")
        if result.get("fumble"):
            parts.append("💥 ПРОМАХ!")
    elif "rolls" in result:
        parts.append(f"🎲 [{', '.join(str(r) for r in result['rolls'])}]")
        if result.get("extra"):
            parts.append(f"+ {result['extra']}")
        if result.get("modifier"):
            parts.append(f"+ {result['modifier']}")
        parts.append(f"= **{result['total']}** урона")
    return " ".join(parts)
