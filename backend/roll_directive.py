"""
Roll directives — the contract between the LLM and the dice engine.

When the narration reaches a point that requires a dice roll (a saving throw,
an attack, a skill check, …) the model is instructed to end its reply with a
single machine-readable directive:

    [[ROLL actor="Торин" type="save_dex" dc="15" reason="уворот от огненной ловушки"]]

The backend detects the directive, strips it from the displayed narration and
switches the session into an "awaiting roll" state until the player submits a
result. This module owns:

  * the default (customizable) trigger rules,
  * generation of the system-prompt section that teaches the model the format,
  * parsing a directive out of model text,
  * a streaming filter that withholds the directive from the live display.
"""

from __future__ import annotations

import re
from typing import Optional


# ── Default trigger rules ────────────────────────────────────────────────────
# Each rule is fully customizable from the UI (stored in PromptConfig.roll_rules_json).
#   category : which family of rolls this rule enables (save | attack | check | initiative)
#   name     : human label shown in the editor
#   when     : description handed to the model — *when* it must request this roll
#   die      : die notation (informational, almost always d20)
#   default_dc: DC suggested to the model when it can't decide (None = no DC, e.g. attack)
#   enabled  : whether the rule is active
DEFAULT_ROLL_RULES = [
    {
        "category": "save",
        "name": "Спасбросок",
        "when": "Персонаж должен избежать или ослабить эффект, который происходит С НИМ: "
                "ловушка, area-заклинание, яд, страх, паралич, падение, взрывная волна.",
        "die": "d20",
        "default_dc": 13,
        "enabled": True,
    },
    {
        "category": "attack",
        "name": "Бросок атаки",
        "when": "Персонаж атакует врага — оружием, заклинанием или приёмом — и исход попадания не предрешён.",
        "die": "d20",
        "default_dc": None,
        "enabled": True,
    },
    {
        "category": "check",
        "name": "Проверка характеристики / навыка",
        "when": "Персонаж пытается сделать что-то сложное и неочевидное: взлом, убеждение, обман, "
                "скрытность, акробатика, восприятие, атлетика, знание.",
        "die": "d20",
        "default_dc": 13,
        "enabled": True,
    },
    {
        "category": "initiative",
        "name": "Инициатива",
        "when": "Начинается бой и нужно определить порядок ходов.",
        "die": "d20",
        "default_dc": None,
        "enabled": True,
    },
]

# Concrete directive `type` tokens exposed per category.
_CATEGORY_TYPES = {
    "save": ["save_str", "save_dex", "save_con", "save_int", "save_wis", "save_cha"],
    "attack": ["attack"],
    "check": ["check_str", "check_dex", "check_con", "check_int", "check_wis", "check_cha"],
    "initiative": ["initiative"],
}


def _enabled_categories(rules: list[dict]) -> list[dict]:
    return [r for r in (rules or DEFAULT_ROLL_RULES) if r.get("enabled", True)]


def _type_lines(active: list[dict]) -> str:
    lines = []
    for r in active:
        types = _CATEGORY_TYPES.get(r.get("category"), [])
        if not types:
            continue
        tokens = " / ".join(types)
        dc = r.get("default_dc")
        dc_hint = f" (если не уверен в сложности — DC {dc})" if dc else ""
        lines.append(f"- **{tokens}** — {r.get('name')}: {r.get('when')}{dc_hint}")
    return "\n".join(lines)


def build_roll_tools(rules: Optional[list[dict]] = None) -> list[dict]:
    """OpenAI-style function schema for native tool-calling (Ollama `tools`)."""
    active = _enabled_categories(rules)
    types = []
    for r in active:
        types.extend(_CATEGORY_TYPES.get(r.get("category"), []))
    if not types:
        return []
    return [{
        "type": "function",
        "function": {
            "name": "request_roll",
            "description": (
                "Запросить у игрока бросок кубика, когда исход не предрешён "
                "(спасбросок, атака, проверка навыка, инициатива). Сначала опиши "
                "ситуацию в обычном тексте, затем вызови эту функцию и остановись — "
                "НЕ описывай результат сам, его пришлёт система."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "actor": {"type": "string", "description": "Имя того, кто бросает"},
                    "type": {"type": "string", "enum": types, "description": "Тип броска"},
                    "dc": {"type": "integer", "description": "Сложность (DC) или КД цели; можно опустить"},
                    "reason": {"type": "string", "description": "Кратко, зачем нужен бросок"},
                },
                "required": ["actor", "type"],
            },
        },
    }]


def spec_from_tool_args(args: dict) -> dict:
    """Normalize request_roll tool arguments into a roll spec."""
    return {
        "actor": str(args.get("actor", "")).strip(),
        "type": _normalize_type(str(args.get("type", ""))),
        "dc": _to_int(args.get("dc")),
        "reason": str(args.get("reason", "")).strip(),
    }


def build_roll_instructions(rules: Optional[list[dict]], use_tools: bool = False) -> str:
    """Render the system-prompt section that teaches the model how to ask for rolls."""
    active = _enabled_categories(rules)
    if not active:
        return ""

    types_block = _type_lines(active)

    if use_tools:
        return f"""

## Механика бросков — функция request_roll
Ты НИКОГДА не решаешь сам, удался ли бросок, и НИКОГДА не выдумываешь, что выпало.
Когда наступает момент, требующий броска:
1. Опиши обстановку и напряжение ДО броска (обычным текстом), но НЕ исход.
2. Вызови функцию **request_roll** с нужными параметрами и остановись.
3. НЕ продолжай сцену и НЕ бросай за игрока — жди результат от системы.

Когда какой тип запрашивать:
{types_block}

После строки «[Результат броска] …» продолжи повествование, опираясь ИМЕННО на этот исход."""

    return f"""

## Механика бросков — СТРОГОЕ ПРАВИЛО
Ты НИКОГДА не решаешь сам, удался ли бросок, и НИКОГДА не придумываешь, что выпало на кубике.
Когда по сюжету наступает момент, требующий броска (см. список ниже), ты ОБЯЗАН:
1. Описать обстановку и напряжение ДО броска, но НЕ его исход.
2. Завершить ответ РОВНО ОДНОЙ директивой строго в таком формате (на отдельной строке, в самом конце):
   [[ROLL actor="<имя того, кто бросает>" type="<тип из списка>" dc="<число или пусто>" reason="<кратко, зачем бросок>"]]
3. Немедленно остановиться. НЕ описывай результат, НЕ продолжай сцену, НЕ бросай за игрока.

Когда какой тип запрашивать:
{types_block}

После того как система пришлёт строку «[Результат броска] …», продолжи повествование,
опираясь ИМЕННО на этот исход (успех/провал, попадание/промах, величину). Только тогда описывай последствия.
Не выводи саму директиву как часть рассказа — она служебная."""


# ── Directive parsing ────────────────────────────────────────────────────────

_DIRECTIVE_RE = re.compile(r"\[\[\s*ROLL\b(.*?)\]\]", re.IGNORECASE | re.DOTALL)
_KV_RE = re.compile(r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s\]]+))')

_VALID_TYPES = {t for types in _CATEGORY_TYPES.values() for t in types}

# Tolerant normalization for sloppy model output.
_TYPE_ALIASES = {
    "save": "save_dex", "saving_throw": "save_dex", "savingthrow": "save_dex",
    "strength": "save_str", "dexterity": "save_dex", "constitution": "save_con",
    "intelligence": "save_int", "wisdom": "save_wis", "charisma": "save_cha",
    "str": "save_str", "dex": "save_dex", "con": "save_con",
    "int": "save_int", "wis": "save_wis", "cha": "save_cha",
    "check": "check_dex", "skill": "check_dex", "ability": "check_dex",
    "atk": "attack", "melee": "attack", "ranged": "attack", "spell_attack": "attack",
    "init": "initiative",
}
_STAT_WORDS = {
    "str": "str", "сил": "str", "strength": "str",
    "dex": "dex", "лов": "dex", "dexterity": "dex",
    "con": "con", "тел": "con", "constitution": "con",
    "int": "int", "инт": "int", "intelligence": "int",
    "wis": "wis", "мдр": "wis", "wisdom": "wis",
    "cha": "cha", "хар": "cha", "charisma": "cha",
}


def _normalize_type(raw: str) -> str:
    t = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if t in _VALID_TYPES:
        return t
    if t in _TYPE_ALIASES:
        return _TYPE_ALIASES[t]
    # e.g. "save_dexterity", "check_strength", "dex_save", "strength_check"
    is_save = "save" in t or "спас" in t
    is_check = "check" in t or "провер" in t or "skill" in t
    for word, stat in _STAT_WORDS.items():
        if word in t:
            if is_check:
                return f"check_{stat}"
            return f"save_{stat}"
    if "attack" in t or "атак" in t:
        return "attack"
    if "init" in t or "инициат" in t:
        return "initiative"
    # generic die like d20 / d6
    m = re.fullmatch(r"d(\d+)", t)
    if m:
        return t
    return t or "save_dex"


def _to_int(val) -> Optional[int]:
    try:
        return int(str(val).strip())
    except (TypeError, ValueError):
        return None


def parse_directive(text: str) -> tuple[Optional[dict], str]:
    """
    Find the first [[ROLL ...]] directive in `text`.

    Returns (spec, cleaned_text). `spec` is None when no directive is present.
    `cleaned_text` always has the directive removed.
    """
    m = _DIRECTIVE_RE.search(text or "")
    if not m:
        return None, text

    fields = {}
    for km in _KV_RE.finditer(m.group(1)):
        key = km.group(1).lower()
        val = km.group(2) or km.group(3) or km.group(4) or ""
        fields[key] = val.strip()

    spec = {
        "actor": fields.get("actor", "").strip(),
        "type": _normalize_type(fields.get("type", "")),
        "dc": _to_int(fields.get("dc")),
        "reason": fields.get("reason", "").strip(),
    }

    cleaned = (text[: m.start()] + text[m.end():]).strip()
    return spec, cleaned


# ── Streaming filter ─────────────────────────────────────────────────────────

class DirectiveStreamFilter:
    """
    Withholds a trailing [[ROLL ...]] directive from the live token stream so it
    never flashes on screen, while still emitting all narration as it arrives.

    Usage:
        filt = DirectiveStreamFilter()
        for chunk in tokens:
            for visible in filt.feed(chunk):
                send(visible)
        spec, cleaned_full, tail = filt.result()
        if tail:
            send(tail)
    """

    _MARKER = "[[ROLL"

    def __init__(self):
        self._full = ""       # entire raw text seen so far
        self._emitted = 0     # length of `_full` already surfaced to the client

    def feed(self, chunk: str):
        if not chunk:
            return
        self._full += chunk
        safe = self._safe_index()
        if safe > self._emitted:
            out = self._full[self._emitted:safe]
            self._emitted = safe
            if out:
                yield out

    def _safe_index(self) -> int:
        """Largest index up to which it is safe to reveal text."""
        idx = self._full.find(self._MARKER)
        if idx != -1:
            # Directive started — never reveal from here on during streaming.
            return idx
        # No full marker yet: hold back a trailing partial of the marker
        # (e.g. text ends with "[[RO") so we don't leak the opening.
        n = len(self._full)
        maxhold = len(self._MARKER) - 1
        for k in range(min(maxhold, n), 0, -1):
            if self._full[n - k:] == self._MARKER[:k]:
                return n - k
        return n

    def result(self) -> tuple[Optional[dict], str, str]:
        """
        Finalize after the stream ends.

        Returns (spec, cleaned_full_text, tail) where `tail` is any remaining
        visible text that was withheld but is NOT part of the directive and
        still needs to be sent to the client.
        """
        spec, cleaned = parse_directive(self._full)
        if spec is None:
            tail = self._full[self._emitted:]
            return None, self._full, tail
        # Everything before the directive start was either already emitted or
        # belongs to `tail`; `cleaned` shares the same prefix as `_full`.
        tail = cleaned[self._emitted:] if len(cleaned) >= self._emitted else ""
        return spec, cleaned, tail


# ── Fallback: detect a roll request written in plain prose ────────────────────
# Local models often ignore the directive format and instead just *write*
# "сделай спасбросок Ловкости". When enforcement is on and no directive was
# emitted, we scan the narration for such phrases so the gate still triggers.

_STAT_ROOTS = [
    (("ловк", "dexterity", "увёрт", "уверт", "акробат", "скрытн", "реакц"), "dex"),
    (("сил", "strength", "атлет", "мускул"), "str"),
    (("тел", "constitution", "выносл", "стойкост", "телосл", "отрав", "яд"), "con"),
    (("интелл", "intelligence", "разум", "знани", "анализ", "логик"), "int"),
    (("мудр", "wisdom", "восприят", "внимател", "проницат", "интуиц", "воля"), "wis"),
    (("харизм", "charisma", "обаян", "убежд", "запугив", "обман", "выступл"), "cha"),
]

_ROLL_VERB_RE = re.compile(
    r"брос(ь|ьте|ить|ок|ка|аем|айте)|кинь(те)?|сделай(те)?\s+(бросок|проверк)|"
    r"проведи(те)?\s+проверк|\broll\b|\bd20\b",
    re.IGNORECASE,
)


def _find_stat(text: str) -> Optional[str]:
    for roots, code in _STAT_ROOTS:
        for r in roots:
            if r in text:
                return code
    return None


def _type_category(roll_type: str) -> Optional[str]:
    if roll_type.startswith("save_"):
        return "save"
    if roll_type.startswith("check_"):
        return "check"
    if roll_type in ("attack", "initiative"):
        return roll_type
    return None


def apply_default_dc(spec: dict, rules: Optional[list[dict]] = None) -> dict:
    """Fill in a DC from the matching rule when the GM didn't specify one."""
    if not spec or spec.get("dc") is not None:
        return spec
    cat = _type_category(spec.get("type", ""))
    for r in _enabled_categories(rules):
        if r.get("category") == cat and r.get("default_dc"):
            spec["dc"] = r["default_dc"]
            break
    return spec


def detect_roll_request(text: str, rules: Optional[list[dict]] = None) -> Optional[dict]:
    """Heuristically detect a roll the GM asked for in plain prose.

    Returns a spec compatible with parse_directive(), or None. Only categories
    that are enabled in `rules` can be detected, mirroring the directive path.
    """
    active = {r.get("category") for r in _enabled_categories(rules)}
    low = (text or "").lower()
    # Asks live near the end of the turn ("...— что делаешь? Сделай бросок.").
    tail = low[-600:]

    has_save = "спасброс" in tail or "spasbros" in tail or "saving throw" in tail
    has_init = "инициатив" in tail
    has_verb = bool(_ROLL_VERB_RE.search(tail))

    if not (has_save or has_init or has_verb):
        return None

    if "save" in active and has_save:
        return {"actor": "", "type": f"save_{_find_stat(tail) or 'dex'}", "dc": None, "reason": "спасбросок"}
    if "initiative" in active and has_init:
        return {"actor": "", "type": "initiative", "dc": None, "reason": "инициатива"}
    if "check" in active and ("провер" in tail or "навык" in tail) and has_verb:
        return {"actor": "", "type": f"check_{_find_stat(tail) or 'dex'}", "dc": None, "reason": "проверка"}
    if "attack" in active and has_verb and ("атак" in tail or "попадан" in tail):
        return {"actor": "", "type": "attack", "dc": None, "reason": "бросок атаки"}
    if "check" in active and has_verb:
        # Generic "брось кубик" with no specifics → an ability check.
        return {"actor": "", "type": f"check_{_find_stat(tail) or 'dex'}", "dc": None, "reason": "бросок"}
    return None
