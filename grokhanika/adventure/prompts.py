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
        "1. НЕ выдумывай новых NPC, существ, предметы, лут и локации. Используй ТОЛЬКО сущности и "
        "факты из блоков «Контекст сцены» и «Факты мира». Если игрок хочет встретить кого-то или "
        "найти предмет — опирайся на переданные карточки. Если подходящих данных нет — обыграй "
        "ситуацию уклончиво, не изобретая конкретных имён/предметов.\n"
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
        '  "search_queries": ["ключевые сущности/темы для поиска в базе: NPC, существа, предметы, '
        'локации; 1-4 строки по-русски"]\n'
        "}\n"
        "Верни только JSON."
    )


def intent_user_prompt(history_brief: str, character_name: str, text: str) -> str:
    return (
        f"Недавний контекст:\n{history_brief or '(начало)'}\n\n"
        f"Реплика игрока (персонаж «{character_name}»): {text}\n\n"
        "Проанализируй намерение и верни JSON по схеме."
    )


# ───────────────────────── контекст хода (динамика) ─────────────────────────


def _facts_block(title: str, cards: Iterable[Card]) -> str:
    lines = [f"- {c.name}: {(c.description or '').strip()}" for c in cards]
    return f"## {title}\n" + "\n".join(lines) if lines else ""


def build_context_block(
    *,
    running_summary: str,
    location: Optional[Card],
    npcs: Iterable[Card],
    items: Iterable[Card],
    lore_facts: Iterable[Card],
    episodic: Iterable[str],
    enrichment: str,
) -> str:
    """Собрать динамический блок контекста для текущего хода ГМ."""
    blocks: list[str] = []
    if running_summary.strip():
        blocks.append(f"## Журнал кампании (что было ранее)\n{running_summary.strip()}")

    scene_lines = []
    if location is not None:
        scene_lines.append(f"Локация: {location.name} — {(location.description or '').strip()}")
    npc_list = list(npcs)
    if npc_list:
        scene_lines.append("Действующие лица:")
        scene_lines += [f"- {c.name}: {(c.description or '').strip()}" for c in npc_list]
    item_list = list(items)
    if item_list:
        scene_lines.append("Предметы в сцене:")
        scene_lines += [f"- {c.name}: {(c.description or '').strip()}" for c in item_list]
    if scene_lines:
        blocks.append("## Контекст сцены (используй этих персонажей и предметы)\n" + "\n".join(scene_lines))

    facts = _facts_block("Факты мира (опирайся на них, не выдумывай иное)", lore_facts)
    if facts:
        blocks.append(facts)

    epi = [e for e in episodic if e and e.strip()]
    if epi:
        blocks.append("## Воспоминания (ранее в приключении)\n" + "\n".join(f"- {e}" for e in epi))

    if enrichment.strip():
        blocks.append(f"## Указание мастеру на этот ход\n{enrichment.strip()}")

    return "\n\n".join(blocks)


def enrichment_for(intent) -> str:
    """Доп. инструкция ГМ по итогам интент-анализа (бросок/бой)."""
    notes: list[str] = []
    if getattr(intent, "combat_initiation", False):
        notes.append(
            "Назревает боевая ситуация. Опиши завязку боя кинематографично и подведи к началу "
            "столкновения, не разрешая бой полностью."
        )
    if getattr(intent, "requires_roll", False):
        label = (getattr(intent, "roll_type", "") or "проверка").strip()
        notes.append(
            f"Действие требует проверки ({label}). Обыграй НАЧАЛО броска в ролиплее: опиши попытку "
            "и предложи игроку сделать бросок, не определяя исход за него."
        )
    return " ".join(notes)
