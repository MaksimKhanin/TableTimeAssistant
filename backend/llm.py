import httpx
import json
import os
from typing import AsyncGenerator

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "llama3")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.8"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "1024"))

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "llm_config.json")

_config = {
    "base_url": LLM_BASE_URL,
    "model": LLM_MODEL,
    "temperature": LLM_TEMPERATURE,
    "max_tokens": LLM_MAX_TOKENS,
    "show_thinking": False,
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
- В начале боя объявляй порядок инициативы (система уже бросила кубики — используй результаты).
- Когда в контексте есть результат броска атаки (hit/miss) — интерпретируй его нарративно.
- Описывай атаки врагов: что именно они делают, как выглядит удар.
- Если враг получает урон — опиши его реакцию. Если падает — дай ему «последние слова».
- Критический удар (nat 20) — нечто особенное и запоминающееся. Промах (nat 1) — комичный или драматичный провал.
- Между ходами задавай ситуацию: "Орк с окровавленным топором бросается на Торина — что делаешь?"

### Правила мастерства
- Действия игроков имеют последствия: мир реагирует и помнит.
- Давай игрокам шанс на успех, но не делай мир безопасным.
- Никогда не говори игроку, что он «не может» что-то сделать — покажи последствия.
- Если игрок пытается что-то сложное — попроси бросок нужного навыка.
- Язык ответа: всегда тот же, на котором пишут игроки.

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
        if self._buf and self._state != "in_think":
            yield ("text", self._buf)
        self._buf = ""


async def stream_response(messages: list[dict]) -> AsyncGenerator[str, None]:
    cfg = get_config()
    url = f"{cfg['base_url']}/api/chat"

    payload = {
        "model": cfg["model"],
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": cfg["temperature"],
            "num_predict": cfg["max_tokens"],
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            if response.status_code >= 400:
                body = await response.aread()
                try:
                    detail = json.loads(body).get("error", body.decode("utf-8", errors="replace"))
                except Exception:
                    detail = body.decode("utf-8", errors="replace")
                raise RuntimeError(f"Ollama {response.status_code}: {detail[:300]}")
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        chunk = data["message"]["content"]
                        if chunk:
                            yield chunk
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue


async def get_full_response(messages: list[dict]) -> str:
    parts = []
    async for chunk in stream_response(messages):
        parts.append(chunk)
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
