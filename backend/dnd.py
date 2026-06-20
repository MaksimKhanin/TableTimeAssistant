import random
from typing import Optional


def roll(sides: int, count: int = 1) -> list[int]:
    return [random.randint(1, sides) for _ in range(count)]


def roll_total(sides: int, count: int = 1, modifier: int = 0) -> int:
    return sum(roll(sides, count)) + modifier


def modifier_from_stat(stat: int) -> int:
    return (stat - 10) // 2


def roll_initiative(dex: int) -> int:
    return roll_total(20, modifier=modifier_from_stat(dex))


def roll_attack(attack_bonus: int = 0) -> dict:
    d = roll(20)[0]
    total = d + attack_bonus
    return {"die": d, "bonus": attack_bonus, "total": total, "critical": d == 20, "fumble": d == 1}


def roll_damage(dice_notation: str, modifier: int = 0) -> dict:
    """Parse notation like '1d6', '2d8', '1d4+2'"""
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


def roll_saving_throw(stat: int, dc: int) -> dict:
    mod = modifier_from_stat(stat)
    d = roll(20)[0]
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
