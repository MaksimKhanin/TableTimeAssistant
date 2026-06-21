import httpx
import json
import os
from typing import AsyncGenerator

import roll_directive

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "llama3")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.8"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "2048"))

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "llm_config.json")

_config = {
    "base_url": LLM_BASE_URL,
    "model": LLM_MODEL,
    "temperature": LLM_TEMPERATURE,
    "max_tokens": LLM_MAX_TOKENS,
    "show_thinking": False,
    "use_tools": False,   # native function-calling for roll requests (model must support it)
}


def _load_persisted():
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH) as f:
                _config.update(json.load(f))
        except Exception:
            pass


def _save_persisted():
    try:
        with open(_CONFIG_PATH, "w") as f:
            json.dump(_config, f, indent=2)
    except Exception:
        pass


_load_persisted()


# Recommended defaults for the two user-editable prompt layers (📜 в UI).
# Seeded for fresh installs; existing installs can paste them manually.
DEFAULT_SYSTEM_ADDENDUM = (
    "Язык: всегда отвечай на том же языке, на котором пишут игроки (по умолчанию — русский), "
    "живым литературным слогом.\n"
    "Тон: насыщенное тёмное фэнтези — напряжение, выбор с ценой, моральная неоднозначность.\n"
    "Стиль: чувственные детали (звук, запах, свет, фактура). *Курсив* — атмосфера и ощущения, "
    "**жирный** — имена, предметы, ключевые слова.\n"
    "Объём: короткие динамичные абзацы в бою и экшене, развёрнутые — в исследовании и диалогах. "
    "Не пиши «простыни» текста."
)

DEFAULT_TURN_REMINDER = (
    "- Оставайся в роли ведущего; никогда не упоминай, что ты ИИ или языковая модель.\n"
    "- ХП и статусы бери ТОЛЬКО из блока [Состояние отряда] выше — не выдумывай числа. "
    "Если ХП = 0 — персонаж при смерти/без сознания, отыграй это.\n"
    "- Не решай сам исход броска: опиши момент, запроси нужный бросок и дождись строки [Результат броска].\n"
    "- Если предлагаешь игрокам выбор действий — НЕ запрашивай бросок в этом же ходу; сначала дождись их решения.\n"
    "- Заканчивай ход короткой ясной развилкой: «Что вы делаете?»"
)


def get_config() -> dict:
    return dict(_config)


def update_config(**kwargs):
    _config.update(kwargs)
    _save_persisted()


def build_system_prompt(
    adventure_description: str,
    gm_role: str,
    characters: list[dict],
    npcs: list[dict] | None = None,
    system_addendum: str = "",
    roll_rules: list[dict] | None = None,
    roll_enforcement: bool = False,
    use_tools: bool = False,
) -> str:
    char_lines = []
    for c in characters:
        line = (
            f"- **{c['name']}** ({c['race']} {c['char_class']}, ур.{c['level']}): "
            f"ХП {c['current_hp']}/{c['max_hp']}, КД {c['armor_class']}"
        )
        if c.get("abilities"):
            line += f". Способности: {c['abilities']}"
        if c.get("background"):
            line += f". Предыстория: {c['background']}"
        char_lines.append(line)

    npc_lines = []
    enemies = []
    allies = []
    for n in (npcs or []):
        entry = f"- **{n['name']}**"
        if n.get("role"):
            entry += f" [{n['role']}]"
        entry += f": ХП {n['current_hp']}/{n['max_hp']}, КД {n['armor_class']}"
        if n.get("personality"):
            entry += f". Характер: {n['personality']}"
        if n.get("voice_style"):
            entry += f". Манера речи: {n['voice_style']}"
        if n.get("is_enemy"):
            enemies.append(entry)
        else:
            allies.append(entry)

    npc_section = ""
    if enemies:
        npc_section += "\n### Враги и антагонисты\n" + "\n".join(enemies)
    if allies:
        npc_section += "\n### Союзники и нейтральные NPC\n" + "\n".join(allies)

    global_extra = f"\n\n## Дополнительные инструкции\n{system_addendum.strip()}" if system_addendum and system_addendum.strip() else ""

    roll_block = roll_directive.build_roll_instructions(roll_rules, use_tools=use_tools) if roll_enforcement else ""

    return f"""Ты — {gm_role}, ведущий интерактивной ролевой игры в стиле Dungeons & Dragons.
Ты НИКОГДА не выходишь из образа и не ссылаешься на то, что ты — языковая модель.{global_extra}

## Мир и завязка
{adventure_description}

## Персонажи игроков
{chr(10).join(char_lines)}
{npc_section}

## Как ты ведёшь игру

### Нарратив и атмосфера
- Описывай мир чувственно: звуки, запахи, свет, температура, текстуры.
- Используй *курсив* для атмосферных описаний и внутренних ощущений.
- Используй **жирный** для имён, важных объектов и ключевых слов.
- Держи темп: короткие абзацы в экшен-сценах, длинные — в исследовании.

### Отыгрыш персонажей (NPC и враги)
- Каждый NPC — живой человек со своей мотивацией, страхами и желаниями.
- Когда NPC говорит, пиши его реплику прямо в диалоге, со своим голосом:
  Пример: *Торговец прищуривается.* "Три золотых, не меньше. Или убирайтесь."
- Враги принимают тактические решения: отступают при потерях, зовут подмогу, используют окружение.
- Злодеи не монологируют без причины — они действуют.
- Если NPC меняет отношение к игрокам из-за их действий — покажи это.

### Боевые ситуации (D&D 5e)
- Объявляй начало боя и порядок ходов; описывай атаки врагов — что именно они делают, как выглядит удар.
- Исходы бросков приходят отдельной строкой «[Результат броска] …». Опирайся ИМЕННО на них и не выдумывай свои попадания/промахи и значения.
- Если враг получает урон — опиши его реакцию. Если падает — дай ему «последние слова».
- Критический удар (nat 20) — нечто особенное и запоминающееся. Промах (nat 1) — комичный или драматичный провал.
- Враги действуют тактически: отступают при потерях, зовут подмогу, используют окружение.

### Источник правды о состоянии (ВАЖНО)
- Перед каждым ходом ты получаешь блок «[Состояние отряда]» с текущими ХП и статусами. Это ЕДИНСТВЕННЫЙ источник правды — не придумывай числа ХП и не противоречь блоку.
- Описывай раны качественно («хромает», «кровь заливает глаз»), а точные ХП отслеживает система.
- Если в блоке ХП персонажа = 0 — он без сознания или при смерти; отыграй это, не давай ему действовать как ни в чём не бывало.

### Правила мастерства
- Действия игроков имеют последствия: мир реагирует и помнит.
- Давай игрокам шанс на успех, но не делай мир безопасным.
- Никогда не говори игроку, что он «не может» что-то сделать — покажи последствия.
- Если игрок пытается что-то сложное — попроси бросок нужного навыка.
- Язык ответа: всегда тот же, на котором пишут игроки.{roll_block}

Начни с атмосферного вступления в мир приключения — погрузи игроков в него с первых строк."""


class ThinkFilter:
    """
    Strips or captures <think>...</think> blocks from a streaming response.

    Qwen3 (and similar models) emit thinking at the very beginning of the
    stream, before the actual answer. The filter buffers chunks until the
    closing tag is found, then switches to pass-through mode.

    Usage: call feed(chunk) for each chunk. It yields (kind, text) pairs
    where kind is "think" (thinking content) or "text" (regular content).
    """

    _OPEN = "<think>"
    _CLOSE = "</think>"

    def __init__(self):
        self._buf = ""
        self._state = "detect"   # detect | in_think | passthrough

    def feed(self, chunk: str):
        if self._state == "passthrough":
            yield ("text", chunk)
            return

        self._buf += chunk

        if self._state == "detect":
            stripped = self._buf.lstrip()
            if stripped.startswith(self._OPEN):
                self._state = "in_think"
            elif len(self._buf) > len(self._OPEN) + 4:
                # No <think> at start — treat entire buffer as regular text
                self._state = "passthrough"
                buf, self._buf = self._buf, ""
                yield ("text", buf)
                return

        if self._state == "in_think":
            close_idx = self._buf.find(self._CLOSE)
            if close_idx >= 0:
                open_idx = self._buf.find(self._OPEN) + len(self._OPEN)
                think_text = self._buf[open_idx:close_idx]
                after = self._buf[close_idx + len(self._CLOSE):]
                self._buf = ""
                self._state = "passthrough"
                if think_text:
                    yield ("think", think_text)
                if after:
                    yield ("text", after)

    def flush(self):
        """Call after stream ends to emit any buffered remainder."""
        if self._buf:
            if self._state == "in_think":
                # Stream ended inside an unclosed <think> block — yield what we have
                open_end = self._buf.find(self._OPEN)
                content = self._buf[open_end + len(self._OPEN):] if open_end >= 0 else self._buf
                if content:
                    yield ("think", content)
            else:
                yield ("text", self._buf)
        self._buf = ""


async def stream_response(messages: list[dict], tools: list | None = None) -> AsyncGenerator[tuple[str, str], None]:
    """Yields (kind, text) tuples where kind is 'text', 'think' or 'roll_tool'.

    When `tools` is provided, native function-calling is enabled; a
    request_roll tool call is surfaced as ('roll_tool', json_args).


    Two robustness behaviours:
      * Auto-continuation — if Ollama stops because it hit the token budget
        (done_reason == "length"), we transparently re-prompt it to resume so
        long narrations are not cut off mid-sentence.
      * Thinking budget — thinking is requested only on the first round. Native
        <think> tokens share the num_predict budget, so a model that "thinks"
        a lot could exhaust it and never emit an answer; the continuation round
        runs with think=false to force the actual reply.
    """
    cfg = get_config()
    show_thinking = cfg.get("show_thinking", False)
    url = f"{cfg['base_url']}/api/chat"

    work = list(messages)
    MAX_CONTINUATIONS = 3

    for attempt in range(MAX_CONTINUATIONS + 1):
        payload = {
            "model": cfg["model"],
            "messages": work,
            "stream": True,
            # Only think on the first pass; continuations must spend the budget on the answer.
            "think": show_thinking and attempt == 0,
            "options": {
                "temperature": cfg["temperature"],
                "num_predict": cfg["max_tokens"],
            },
        }
        # Offer tools only on the first round (a continuation is just resuming text).
        if tools and attempt == 0:
            payload["tools"] = tools

        finish_reason = "stop"
        had_thinking = False
        round_text = ""
        tool_calls_collected = []

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    try:
                        detail = json.loads(body).get("error", body.decode("utf-8", errors="replace"))
                    except Exception:
                        detail = body.decode("utf-8", errors="replace")
                    raise RuntimeError(f"Ollama {response.status_code}: {detail[:300]}")

                filt = ThinkFilter()
                got_native_thinking = False
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = data.get("message", {})

                    tcs = msg.get("tool_calls")
                    if tcs:
                        tool_calls_collected.extend(tcs)

                    # Ollama native thinking field (Ollama ≥0.9 with think:true)
                    thinking = msg.get("thinking") or ""
                    if thinking:
                        got_native_thinking = True
                        had_thinking = True
                        yield ("think", thinking)

                    content = msg.get("content") or ""
                    if content:
                        if got_native_thinking:
                            # Native thinking already separated: content is the actual response
                            round_text += content
                            yield ("text", content)
                        else:
                            # Fallback: model embeds <think> tags inside content stream
                            for kind, text in filt.feed(content):
                                if kind == "text":
                                    round_text += text
                                else:
                                    had_thinking = True
                                yield (kind, text)

                    if data.get("done"):
                        finish_reason = data.get("done_reason") or "stop"
                        if not got_native_thinking:
                            for kind, text in filt.flush():
                                if kind == "text":
                                    round_text += text
                                else:
                                    had_thinking = True
                                yield (kind, text)
                        break

        # Native function call wins — emit it and stop (no continuation needed).
        emitted_tool = False
        for tc in tool_calls_collected:
            fn = tc.get("function", {}) if isinstance(tc, dict) else {}
            if fn.get("name") == "request_roll":
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                yield ("roll_tool", json.dumps(args))
                emitted_tool = True
                break
        if emitted_tool:
            break

        truncated = finish_reason == "length"
        think_only = had_thinking and not round_text.strip()
        if not (truncated or think_only) or attempt == MAX_CONTINUATIONS:
            break

        if round_text.strip():
            # Resume exactly where the model left off.
            work = work + [
                {"role": "assistant", "content": round_text},
                {"role": "user", "content": "Продолжи ровно с места обрыва — не повторяй уже написанное и не начинай заново."},
            ]
        # else: the round was thinking-only with no answer — retry the same
        # messages with think disabled (attempt > 0) to force a reply.


async def get_full_response(messages: list[dict]) -> str:
    parts = []
    async for kind, text in stream_response(messages):
        if kind == "text":
            parts.append(text)
    return "".join(parts)


async def check_connection() -> dict:
    cfg = get_config()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{cfg['base_url']}/api/tags")
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                return {"ok": True, "models": models}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "unexpected response"}


async def list_models() -> list[str]:
    result = await check_connection()
    return result.get("models", [])
