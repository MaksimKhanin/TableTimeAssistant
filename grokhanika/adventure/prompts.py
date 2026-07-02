"""Сборка системных промтов: персона ГМ, анализатор намерений, контекст хода.

Стабильная часть (персона + правила) идёт первой — локальные серверы (vLLM/Ollama)
кешируют общий префикс. Динамический контекст (сводка/сцена/факты/воспоминания)
собирается на каждый ход.

Статичный текст шаблонов (персона ГМ, схема интент-анализа, заголовки блоков
контекста, заметки ``enrichment_for``, итог боя) вынесен в
``grokhanika/data/prompts.yaml`` — здесь только сборка (циклы/условия) вокруг
него. См. :func:`load_templates`/:func:`fill_template`.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

import yaml

from ..db.models import AdventureSession, Card

_PROMPTS_PATH = Path(__file__).resolve().parent.parent / "data" / "prompts.yaml"

# допустимые типы намерений (для интент-анализа)
INTENT_TYPES = (
    "dialogue",       # разговор/реплика
    "movement",       # перемещение между местами
    "exploration",    # осмотр/исследование
    "combat",         # атака/начало боя
    "skill_check",    # действие с проверкой/спасброском
    "item_use",       # использование предмета
    "other",
)


@lru_cache(maxsize=1)
def load_templates() -> dict:
    return yaml.safe_load(_PROMPTS_PATH.read_text(encoding="utf-8"))


def fill_template(template: str, **values: str) -> str:
    """Простая подстановка ``{ключ}`` — без ``str.format()``, чтобы не спотыкаться

    о литеральные фигурные скобки в тексте промтов (например, JSON-схема
    в шаблоне анализатора намерений).
    """
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


# ───────────────────────── персона ГМ ─────────────────────────


def build_system_prompt(adv: AdventureSession) -> str:
    """Стабильный system-промт ГМ (сохраняется в ``adv.system_prompt`` при старте)."""
    party = ", ".join(c.name for c in adv.party) or "—"
    t = load_templates()
    setup = fill_template(
        t["gm_setup_template"],
        adventure_type=adv.adventure_type,
        description=adv.description or "—",
        goal=adv.goal or "—",
        party=party,
    )
    return f"{t['gm_persona']}\n{setup}"


# ───────────────────────── анализатор намерений ─────────────────────────


def intent_system_prompt() -> str:
    types = ", ".join(INTENT_TYPES)
    return fill_template(load_templates()["intent_system_template"], intent_types=types)


def intent_user_prompt(history_brief: str, character_name: str, text: str) -> str:
    return fill_template(
        load_templates()["intent_user_template"],
        history_brief=history_brief or "(начало)",
        character_name=character_name,
        text=text,
    )


def opening_system_prompt() -> str:
    return load_templates()["opening_system_template"]


def opening_user_prompt(description: str, goal: str) -> str:
    return fill_template(
        load_templates()["opening_user_template"],
        description=description or "—",
        goal=goal or "—",
    )


# ───────────────────────── контекст хода (динамика) ─────────────────────────


def _facts_block(title: str, cards: Iterable[Card]) -> str:
    lines = [f"- {c.name}: {(c.description or '').strip()}" for c in cards]
    return f"## {title}\n" + "\n".join(lines) if lines else ""


def build_context_block(
    *,
    running_summary: str,
    location: Optional[dict],
    npcs: Iterable[dict],
    lore_facts: Iterable[Card],
    episodic: Iterable[str],
    enrichment: str,
) -> str:
    """Собрать динамический блок контекста для текущего хода ГМ.

    ``location`` — свободный текст ``{"name", "description"}`` (без привязки к
    карточкам). ``npcs`` — ``[{"card": Card, "count": int}]``: количество
    зафиксировано детерминированно интент-анализатором, ГМ должен ему следовать.
    """
    t = load_templates()
    blocks: list[str] = []
    if running_summary.strip():
        blocks.append(f"{t['context_running_summary_heading']}\n{running_summary.strip()}")

    scene_lines = []
    if location:
        scene_lines.append(
            fill_template(
                t["context_location_line_template"],
                name=location["name"],
                description=(location.get("description") or "").strip(),
            )
        )
    npc_list = list(npcs)
    if npc_list:
        scene_lines.append(t["context_npc_heading"])
        for entry in npc_list:
            card = entry["card"]
            count = int(entry.get("count", 1))
            suffix = f" (x{count})" if count > 1 else ""
            scene_lines.append(f"- {card.name}{suffix}: {(card.description or '').strip()}")
    if scene_lines:
        blocks.append(t["context_scene_heading"] + "\n" + "\n".join(scene_lines))

    facts = _facts_block(t["context_lore_title"], lore_facts)
    if facts:
        blocks.append(facts)

    epi = [e for e in episodic if e and e.strip()]
    if epi:
        blocks.append(t["context_episodic_heading"] + "\n" + "\n".join(f"- {e}" for e in epi))

    if enrichment.strip():
        blocks.append(f"{t['context_enrichment_heading']}\n{enrichment.strip()}")

    return "\n\n".join(blocks)


def enrichment_for(intent, *, combat_ready: bool = True) -> str:
    """Доп. инструкция ГМ по итогам интент-анализа (бросок/бой).

    ``combat_ready`` — нашлись ли в каталоге подходящие противники для намерения
    ``combat_initiation``. Если нет — сцену нельзя оставлять «подвешенной»: рассказчику
    даётся не завязка боя, а сюжетное объяснение, почему стычка не состоялась.

    Если бой не состоялся (``combat_initiation`` и не ``combat_ready``), инструкция про
    бросок подавляется: ``requires_roll`` в этом случае почти всегда относится именно к
    броску атаки несостоявшегося боя, а без реального противника обрабатывать его
    некому — команда «сделай бросок» и «стычки не было» иначе противоречат друг другу.
    """
    t = load_templates()
    notes: list[str] = []
    combat_deflected = False
    if getattr(intent, "combat_initiation", False):
        if combat_ready:
            notes.append(t["enrichment_combat_ready"])
        else:
            notes.append(t["enrichment_combat_deflected"])
            combat_deflected = True
    if getattr(intent, "requires_roll", False) and not combat_deflected:
        label = (getattr(intent, "roll_type", "") or "проверка").strip()
        notes.append(fill_template(t["enrichment_requires_roll_template"], label=label))
    return " ".join(notes)


# ───────────────────────── итог проверки (бросок кубика) ─────────────────────────

_ROLL_OUTCOME_HINTS = {
    "crit": "блестящий, безоговорочный успех (натуральная 20) — попытка удаётся ярче, чем ожидалось.",
    "success": "попытка удалась — опиши успех и его последствия.",
    "fail": "попытка провалилась — опиши неудачу и её последствия, не наказывая игрока сверх меры.",
    "fumble": "критический провал (натуральная 1) — попытка проваливается зрелищно, с осложнением.",
}


def roll_outcome_kickoff(*, label: str, value: int, difficulty: int, outcome: str) -> str:
    """Реплика-затравка для ГМ: игрок сделал бросок проверки, рассказать исход."""
    outcome_ru = {
        "crit": "критический успех",
        "success": "успех",
        "fail": "провал",
        "fumble": "критический провал",
    }.get(outcome, outcome)
    return fill_template(
        load_templates()["roll_outcome_kickoff_template"],
        label=label or "проверка",
        value=str(value),
        difficulty=str(difficulty) if difficulty > 0 else "по усмотрению ГМ",
        outcome=outcome_ru,
        outcome_hint=_ROLL_OUTCOME_HINTS.get(outcome, "исход решает ГМ."),
    )


# ───────────────────────── итог боя ─────────────────────────

_ENDED_BY_RU = {
    "rout": "разгром одной из сторон",
    "negotiation": "переговоры/капитуляция",
    "timeout": "бой затянулся и был прерван",
    "draw": "ничья",
}


def combat_outcome_kickoff(outcome: dict) -> str:
    """Реплика-затравка для ГМ: подвести итог только что закончившегося боя.

    ``outcome`` — словарь в формате ответа боевого API (``winner_label``,
    ``ended_by``, ``survivors``, ``log``): см. ``web/simulation.py``.
    """
    winner_label = outcome.get("winner_label")
    ended_by = _ENDED_BY_RU.get(outcome.get("ended_by", ""), outcome.get("ended_by", ""))
    survivors = outcome.get("survivors") or {}
    survivor_lines = []
    for side, names in survivors.items():
        if names:
            survivor_lines.append(f"{side}: {', '.join(names)}")
    survivors_text = "; ".join(survivor_lines) if survivor_lines else "выживших не осталось"
    log_tail = "\n".join(outcome.get("log") or [])

    t = load_templates()
    outcome_desc = f"победа стороны «{winner_label}»" if winner_label else "ничья"
    summary = fill_template(
        t["combat_outcome_summary_template"],
        outcome_desc=outcome_desc,
        ended_by=ended_by,
        survivors_text=survivors_text,
        log_tail=log_tail,
    )
    return f"{t['combat_outcome_intro']}\n{summary}"
