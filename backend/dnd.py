import random
from typing import Optional


def roll(sides: int, count: int = 1) -> list[int]:
    return [random.randint(1, sides) for _ in range(count)]


def roll_total(sides: int, count: int = 1, modifier: int = 0) -> int:
    return sum(roll(sides, count)) + modifier


def modifier_from_stat(stat: int) -> int:
    return (stat - 10) // 2


def _d20(die: Optional[int] = None) -> int:
    """Return a d20 face — either the value the player physically rolled
    (hybrid mode) or a fresh random roll. Clamped to 1..20."""
    if die is not None:
        return max(1, min(20, int(die)))
    return roll(20)[0]


def roll_initiative(dex: int, die: Optional[int] = None) -> dict:
    d = _d20(die)
    mod = modifier_from_stat(dex)
    return {"die": d, "bonus": mod, "total": d + mod}


def roll_attack(attack_bonus: int = 0, die: Optional[int] = None) -> dict:
    d = _d20(die)
    total = d + attack_bonus
    return {"die": d, "bonus": attack_bonus, "total": total, "critical": d == 20, "fumble": d == 1}


def roll_ability_check(stat: int, dc: Optional[int] = None, die: Optional[int] = None) -> dict:
    mod = modifier_from_stat(stat)
    d = _d20(die)
    total = d + mod
    out = {"die": d, "modifier": mod, "total": total, "critical": d == 20, "fumble": d == 1}
    if dc is not None:
        out["dc"] = dc
        out["success"] = total >= dc
    return out


def roll_damage(dice_notation: str, modifier: int = 0, manual_total: Optional[int] = None) -> dict:
    """Parse notation like '1d6', '2d8', '1d4+2'. If manual_total is given
    (hybrid mode — player rolled physical dice), use it verbatim."""
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
        count, sides = 1, 6

    rolls = roll(sides, count)
    total = sum(rolls) + extra + modifier
    return {"rolls": rolls, "extra": extra, "modifier": modifier, "total": max(0, total)}


def roll_saving_throw(stat: int, dc: int, die: Optional[int] = None) -> dict:
    mod = modifier_from_stat(stat)
    d = _d20(die)
    total = d + mod
    return {"die": d, "modifier": mod, "total": total, "dc": dc, "success": total >= dc}


COMBAT_ACTIONS = ["Attack", "Dash", "Disengage", "Dodge", "Help", "Hide", "Ready", "Search", "Use Object"]


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
        parts.append(f"= **{result['total']}** урона")
    return " ".join(parts)
