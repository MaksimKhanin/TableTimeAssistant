"""
Utility referee — the rules brain that the narration model is NOT allowed to be.

Ported and adapted from the dnd-llm-game project's two-model design: a small,
low-temperature "utility" model decides game mechanics as strict JSON, while the
creative model only writes prose. This removes the unreliability of asking a
local narration model to self-emit roll directives.

Two decision points (both run on the utility model via llm.chat_json):

  * decide_player_roll()  — PRE-PASS, before any narration. Reads the player's
    declared action and decides whether it needs a check. This is the decisive
    fix for "the narrative implied a roll but none happened": the roll is decided
    from the action, not hoped-for inside the prose.

  * analyze_narration()   — POST-PASS, after the GM turn streams. Reads the
    generated narration and returns, in one call:
      - roll   : a roll the *narration* implies (enemy attack, trap, forced save),
      - hp      : HP deltas to apply (damage / healing),
      - scene   : compact UI state {location, objective, summary, choices}.

Every field has a deterministic fallback so a flaky/garbage LLM response never
breaks the turn: roll → roll_directive prose detection, choices → regex parse of
a "Choices:" block → static defaults, hp → empty list.
"""

from __future__ import annotations

import re
from typing import Any, Optional

import llm
import roll_directive
from prompts_config import (
    DEFAULT_REFEREE_DECIDE_SYSTEM,
    DEFAULT_REFEREE_ANALYZE_SYSTEM,
    REFEREE_DECIDE_USER_TEMPLATE,
    REFEREE_ANALYZE_USER_TEMPLATE,
)


DEFAULT_CHOICES = [
    "Осмотреться вокруг.",
    "Задать уточняющий вопрос.",
    "Осторожно двигаться дальше.",
]


# ── Type helpers ──────────────────────────────────────────────────────────────

def _allowed_types(rules: Optional[list[dict]]) -> list[str]:
    """Concrete directive `type` tokens for the categories enabled in `rules`."""
    types: list[str] = []
    for r in roll_directive._enabled_categories(rules):
        types.extend(roll_directive._CATEGORY_TYPES.get(r.get("category"), []))
    return types or list({t for ts in roll_directive._CATEGORY_TYPES.values() for t in ts})


def _clamp_dc(value: Any) -> Optional[int]:
    try:
        return max(5, min(25, int(value)))
    except (TypeError, ValueError):
        return None


# ── Deterministic player-action fallback ──────────────────────────────────────
# Maps Russian/English action roots to a (roll type, default DC). Only used when
# the utility model call fails outright; otherwise the model's decision wins.
_ACTION_RULES: list[tuple[tuple[str, ...], str, int]] = [
    (("крад", "скрыт", "подкрад", "пряч", "тих", "незаметн", "stealth", "sneak", "hide"),
     "check_dex", 13),
    (("убежд", "уговар", "угова", "договор", "обман", "вр", "соблазн", "запуг", "блеф",
      "persuade", "deceive", "intimidate", "lie"),
     "check_cha", 13),
    (("обыщ", "обыскив", "осматрив", "иссл", "изуч", "анализ", "разгад", "investigate", "search", "study"),
     "check_int", 12),
    (("замеч", "прислуш", "высматрив", "вгляд", "чувству", "насторож", "perception", "notice", "listen", "spot"),
     "check_wis", 12),
    (("взбира", "караб", "лез", "выламыв", "ломаю", "толка", "поднима", "тащ", "силой",
      "climb", "force", "break", "lift", "shove"),
     "check_str", 13),
    (("прыга", "уворач", "балансир", "акроб", "проскольз", "jump", "dodge", "acrobat"),
     "check_dex", 13),
    (("атак", "удар", "бью", "руб", "стрел", "колю", "напад", "кастую", "закл",
      "attack", "strike", "shoot", "stab", "cast"),
     "attack", 0),
]


def _fallback_player_roll(action: str, actor_name: str) -> Optional[dict]:
    low = (action or "").lower()
    for roots, rtype, dc in _ACTION_RULES:
        if any(root in low for root in roots):
            spec = {
                "actor": actor_name,
                "type": rtype,
                "dc": dc if dc else None,
                "reason": _short_reason(action),
                "narration": "",
            }
            return spec
    return None


def _short_reason(action: str) -> str:
    clean = re.sub(r"\s+", " ", (action or "")).strip().rstrip(".")
    if len(clean) > 90:
        clean = clean[:90].rsplit(" ", 1)[0]
    return clean


# ── PRE-PASS: decide a roll from the player's declared action ──────────────────

async def decide_player_roll(
    action: str,
    context: str,
    actor_name: str,
    rules: Optional[list[dict]],
    *,
    system_override: str = "",
) -> Optional[dict]:
    """Return a roll spec {actor, type, dc, reason, narration} if the player's
    action needs a check, else None. Runs BEFORE narration."""
    types = " / ".join(_allowed_types(rules))
    system = system_override.strip() if system_override and system_override.strip() else DEFAULT_REFEREE_DECIDE_SYSTEM
    user = REFEREE_DECIDE_USER_TEMPLATE.format(context=context, action=action, types=types)

    # Sentinel: empty dict means the utility call failed → use keyword fallback.
    decision = await llm.chat_json(system, user, {})
    if not decision:
        return _fallback_player_roll(action, actor_name)

    if not bool(decision.get("requires_roll")):
        return None

    fb = _fallback_player_roll(action, actor_name) or {}
    rtype = roll_directive._normalize_type(
        str(decision.get("type") or fb.get("type") or "check_dex")
    )
    spec = {
        "actor": actor_name,
        "type": rtype,
        "dc": _clamp_dc(decision.get("dc")) if decision.get("dc") is not None else fb.get("dc"),
        "reason": (str(decision.get("reason") or "").strip() or fb.get("reason") or _short_reason(action)),
        "narration": str(decision.get("narration") or "").strip(),
    }
    return spec


# ── POST-PASS: rolls + HP + scene state from the GM narration ──────────────────

async def analyze_narration(
    gm_text: str,
    context: str,
    rules: Optional[list[dict]],
    prev_scene: Optional[dict],
    *,
    want_roll: bool,
    want_hp: bool,
    system_override: str = "",
) -> dict:
    """One utility call that converts the GM narration into:
      {"roll": spec|None, "hp": [..], "scene": {location, objective, summary, choices}}
    """
    prev = prev_scene or {}
    fallback_choices = extract_choices(gm_text) or clean_choice_list(prev.get("choices")) or list(DEFAULT_CHOICES)
    types = " / ".join(_allowed_types(rules))

    fallback = {
        "roll": {"requires_roll": False},
        "hp": [],
        "location": prev.get("location", ""),
        "objective": prev.get("objective", ""),
        "summary": prev.get("summary", ""),
        "choices": fallback_choices,
    }

    system = system_override.strip() if system_override and system_override.strip() else DEFAULT_REFEREE_ANALYZE_SYSTEM
    user = REFEREE_ANALYZE_USER_TEMPLATE.format(
        gm_text=gm_text, context=context, types=types,
    )

    data = await llm.chat_json(system, user, fallback)

    result: dict[str, Any] = {"roll": None, "hp": [], "scene": None}

    # — roll —
    if want_roll:
        roll = data.get("roll") if isinstance(data.get("roll"), dict) else {}
        if roll and bool(roll.get("requires_roll")):
            result["roll"] = {
                "actor": str(roll.get("actor") or "").strip(),
                "type": roll_directive._normalize_type(str(roll.get("type") or "")),
                "dc": _clamp_dc(roll.get("dc")),
                "reason": str(roll.get("reason") or "").strip(),
            }
        else:
            # Deterministic safety net: scan the prose for a roll the GM asked for.
            result["roll"] = roll_directive.detect_roll_request(gm_text, rules)

    # — hp —
    if want_hp:
        result["hp"] = _clean_hp(data.get("hp"))

    # — scene —
    result["scene"] = {
        "location": clean_extracted_text(data.get("location"), prev.get("location", ""), 120, "Неизвестная локация"),
        "objective": clean_extracted_text(data.get("objective"), prev.get("objective", ""), 180, "Выбери следующий ход."),
        "summary": clean_extracted_text(
            data.get("summary"),
            " ".join(_format_summary_source(gm_text).split()[:42]) or prev.get("summary", ""),
            260,
            "Сцена разворачивается.",
        ),
        "choices": (clean_choice_list(data.get("choices")) or fallback_choices)[:4],
    }
    return result


def _clean_hp(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    out: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        target = str(item.get("target") or "").strip()
        try:
            delta = int(item.get("delta"))
        except (TypeError, ValueError):
            continue
        if not target or delta == 0:
            continue
        out.append({"target": target, "delta": delta, "reason": str(item.get("reason") or "").strip()})
    return out


# ── Choices / scene-text cleaning (ported from dnd-llm-game service.py) ────────

def extract_choices(text: str) -> list[str]:
    """Tier-1: parse a numbered/bulleted 'Choices:' / 'Что дальше:' block from prose."""
    cleaned = (text or "").replace("\r\n", "\n")
    section = re.search(
        r"(?:^|\n)\s*(?:choices|что (?:вы )?делаете|что дальше|варианты)[\?:]?\s*\n(?P<body>.*)$",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if section:
        cleaned = section.group("body")
    patterns = [
        r"^\s*(?:\d+[\).\:]|-|\*|•)\s+(?:\*\*)?(.*?)(?:\*\*)?\s*$",
        r"^\s*(?:вариант|option)\s+\d+[\:\).-]\s+(.*?)\s*$",
    ]
    choices: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for pattern in patterns:
            match = re.match(pattern, stripped, flags=re.IGNORECASE)
            if match:
                choice = clean_choice_value(match.group(1))
                choice = re.sub(r"^\*\*|\*\*$", "", choice).strip()
                choice = re.sub(r"\*\*", "", choice).strip()
                choice = re.sub(r"^\s*[-–—]\s*", "", choice).strip()
                if 4 <= len(choice) <= 220 and not is_placeholder_choice(choice):
                    choices.append(choice)
                break
    deduped: list[str] = []
    for choice in choices:
        if choice.lower() not in {c.lower() for c in deduped}:
            deduped.append(choice)
    return deduped[:4]


def clean_choice_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("action", "choice", "text", "label", "description"):
            if key in value:
                return clean_choice_value(value[key])
        return ""
    text = str(value or "").strip()
    object_match = re.search(
        r"""["']?(?:action|choice|text|label)["']?\s*:\s*["'](?P<value>.+?)["']\s*[},]?$""",
        text,
        flags=re.IGNORECASE,
    )
    if object_match:
        text = object_match.group("value")
    text = re.sub(r"^\s*(?:\d+[\).\:]|-|\*|•)\s+", "", text).strip()
    text = re.sub(r"^\{+|\}+$", "", text).strip()
    text = re.sub(r"^['\"]+|['\"]+$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def clean_choice_list(value: Any) -> list[str]:
    if isinstance(value, dict):
        value = value.get("choices") or value.get("actions") or value.get("options") or []
    if not isinstance(value, list):
        return []
    choices = [clean_choice_value(item) for item in value]
    return [c for c in choices if c and not is_placeholder_choice(c)]


def is_placeholder_choice(choice: str) -> bool:
    normalized = (choice or "").lower()
    blocked = [
        "a concise action", "another concise action", "specific playable action",
        "the player can take", "option ", "вариант действия", "конкретное действие",
    ]
    return any(text in normalized for text in blocked)


def is_placeholder_text(value: str) -> bool:
    blocked = [
        "short current location", "current immediate objective", "one sentence scene summary",
        "scene summary", "current location", "место действия", "цель отряда", "суть сцены",
    ]
    normalized = (value or "").lower()
    return any(item in normalized for item in blocked)


def clean_extracted_text(value: Any, fallback: str, limit: int, default: str) -> str:
    text = str(value or "").strip()
    if not text or is_placeholder_text(text):
        text = fallback
    if not text or is_placeholder_text(text):
        text = default
    return text[:limit]


def _format_summary_source(text: str) -> str:
    return re.sub(r"(\*\*|#{1,6}\s|---+)", "", text or "").strip()
