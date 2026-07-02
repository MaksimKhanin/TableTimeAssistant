"""Сборка системных промтов: персона ГМ, анализатор намерений, контекст хода.

Стабильная часть (персона + правила) идёт первой — локальные серверы (vLLM/Ollama)
кешируют общий префикс. Динамический контекст (сводка/сцена/факты/воспоминания)
собирается на каждый ход.
"""
from __future__ import annotations

from typing import Iterable, Optional

from ..db.models import AdventureSession, Card

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


# ───────────────────────── персона ГМ ─────────────────────────


def build_system_prompt(adv: AdventureSession) -> str:
    """Стабильный system-промт ГМ (сохраняется в ``adv.system_prompt`` при старте)."""
    party = ", ".join(c.name for c in adv.party) or "—"
    return (
        "Ты — Гейм-мастер (рассказчик) текстовой ролевой игры в тёмном фэнтези-мире Гроханика.\n"
        "Ты ведёшь повествование живо и атмосферно, по-русски, как опытный мастер настольной RPG.\n\n"
        "ЖЁСТКИЕ ПРАВИЛА:\n"
        "1. НЕ выдумывай новых NPC, существ и локаций, отличных от переданных. Используй ТОЛЬКО "
        "сущности и факты из блоков «Контекст сцены» и «Факты мира». Если в сцене у NPC указано "
        "количество (например, «(x2)») — держись именно этого числа, не увеличивай и не уменьшай "
        "его сам. Если подходящих данных нет — обыграй ситуацию уклончиво, не изобретая конкретных "
        "имён. Предметы/лут сцена не отслеживает — здесь можно свободно и уместно описывать находки.\n"
        "2. Не играй за игровых персонажей партии и не принимай решений за них. Описывай мир, "
        "реакции NPC и последствия действий.\n"
        "3. Когда действие требует проверки или спасброска — обыгрывай НАЧАЛО броска в ролиплее и "
        "предлагай игроку бросок, не определяя исход за него.\n"
        "4. Держись завязки и главной цели партии. Пиши связно, 1–3 абзаца за ход.\n\n"
        f"Тип приключения: {adv.adventure_type}\n"
        f"Завязка (от игроков): {adv.description or '—'}\n"
        f"Главная цель партии: {adv.goal or '—'}\n"
        f"Состав партии: {party}\n"
    )


# ───────────────────────── анализатор намерений ─────────────────────────


def intent_system_prompt() -> str:
    types = ", ".join(INTENT_TYPES)
    return (
        "Ты — анализатор намерений игрока в текстовой RPG. По последней реплике игрока определи "
        "намерение и верни СТРОГО один JSON-объект без каких-либо пояснений и текста вокруг.\n"
        "Схема:\n"
        "{\n"
        f'  "intent_type": один из [{types}],\n'
        '  "requires_roll": true|false,   // нужна ли проверка/спасбросок (взлом, скрытность, '
        "убеждение, акробатика и т.п.)\n"
        '  "roll_type": "краткая метка проверки или пустая строка",\n'
        '  "combat_initiation": true|false,  // игрок начинает бой/атакует\n'
        '  "leaves_location": true|false,    // игрок покидает текущую локацию/перемещается\n'
        '  "location_name": "название НОВОЙ локации, если сцена перемещается в другое место '
        '(leaves_location=true); иначе пустая строка — текущая локация не меняется",\n'
        '  "location_description": "1 фраза описания новой локации; иначе пустая строка",\n'
        '  "npc_mentions": [{"query": "кто именно появляется в кадре, по-русски, кратко, как для '
        'поиска в каталоге существ/персонажей", "count": число_таких_NPC_в_кадре}], '
        "// ТОЛЬКО реально появляющиеся/присутствующие в сцене NPC; если реплика их не подразумевает "
        "— пустой список\n"
        '  "search_queries": ["ключевые темы для поиска ФАКТОВ МИРА (лор, история, география); '
        'НЕ для NPC — 1-4 строки по-русски"],\n'
        '  "enemy_query": "если combat_initiation=true: кого искать в каталоге существ/противников '
        'по контексту сцены (по-русски, кратко); иначе пустая строка",\n'
        '  "enemy_count": число противников, подходящее по контексту (если combat_initiation=true; '
        "иначе 0)\n"
        "}\n"
        "Верни только JSON."
    )


def intent_user_prompt(history_brief: str, character_name: str, text: str) -> str:
    return (
        f"Недавний контекст:\n{history_brief or '(начало)'}\n\n"
        f"Реплика игрока (персонаж «{character_name}»): {text}\n\n"
        "Проанализируй намерение и верни JSON по схеме."
    )


def opening_system_prompt() -> str:
    return (
        "Ты помогаешь Гейм-мастеру задать стартовую сцену текстовой RPG по завязке и цели партии. "
        "Верни СТРОГО один JSON-объект без пояснений и текста вокруг:\n"
        "{\n"
        '  "location_name": "краткое название стартовой локации",\n'
        '  "location_description": "1 фраза описания места",\n'
        '  "npc_mentions": [{"query": "кто присутствует изначально, по-русски, кратко, как для '
        'поиска в каталоге существ/персонажей", "count": число_таких_NPC}]\n'
        "}\n"
        "Если по завязке нет явных начальных NPC — верни пустой список npc_mentions. Верни только "
        "JSON."
    )


def opening_user_prompt(description: str, goal: str) -> str:
    return (
        f"Завязка (от игроков): {description or '—'}\n"
        f"Главная цель партии: {goal or '—'}\n\n"
        "Задай стартовую локацию и (если применимо) начальных NPC."
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
    blocks: list[str] = []
    if running_summary.strip():
        blocks.append(f"## Журнал кампании (что было ранее)\n{running_summary.strip()}")

    scene_lines = []
    if location:
        scene_lines.append(f"Локация: {location['name']} — {(location.get('description') or '').strip()}")
    npc_list = list(npcs)
    if npc_list:
        scene_lines.append("Действующие лица:")
        for entry in npc_list:
            card = entry["card"]
            count = int(entry.get("count", 1))
            suffix = f" (x{count})" if count > 1 else ""
            scene_lines.append(f"- {card.name}{suffix}: {(card.description or '').strip()}")
    if scene_lines:
        blocks.append("## Контекст сцены (используй именно этих персонажей и это количество)\n" + "\n".join(scene_lines))

    facts = _facts_block("Факты мира (опирайся на них, не выдумывай иное)", lore_facts)
    if facts:
        blocks.append(facts)

    epi = [e for e in episodic if e and e.strip()]
    if epi:
        blocks.append("## Воспоминания (ранее в приключении)\n" + "\n".join(f"- {e}" for e in epi))

    if enrichment.strip():
        blocks.append(f"## Указание мастеру на этот ход\n{enrichment.strip()}")

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
    notes: list[str] = []
    combat_deflected = False
    if getattr(intent, "combat_initiation", False):
        if combat_ready:
            notes.append(
                "Назревает боевая ситуация. Опиши завязку боя кинематографично и подведи к началу "
                "столкновения, не разрешая бой полностью."
            )
        else:
            notes.append(
                "Игрок пытается начать бой, но подходящего противника в этой сцене нет. Не отказывай "
                "игроку впрямую и не оставляй сцену «подвешенной» — сюжетно объясни, почему стычка не "
                "состоялась (враг сбежал, угроза оказалась ложной, цель ускользнула и т.п.), и веди "
                "повествование дальше."
            )
            combat_deflected = True
    if getattr(intent, "requires_roll", False) and not combat_deflected:
        label = (getattr(intent, "roll_type", "") or "проверка").strip()
        notes.append(
            f"Действие требует проверки ({label}). Обыграй НАЧАЛО броска в ролиплее: опиши попытку "
            "и предложи игроку сделать бросок, не определяя исход за него."
        )
    return " ".join(notes)


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

    return (
        "Бой только что завершился. Подведи итог сцены как ГМ: кинематографично опиши развязку "
        "и последствия схватки, опираясь на факты ниже. Не повторяй хронику дословно — перескажи "
        "художественно, 1-3 абзаца, и предложи игрокам, что делать дальше.\n\n"
        f"Итог: {'победа стороны «' + winner_label + '»' if winner_label else 'ничья'} "
        f"({ended_by}).\n"
        f"Кто уцелел: {survivors_text}.\n"
        f"Хроника боя:\n{log_tail}"
    )
