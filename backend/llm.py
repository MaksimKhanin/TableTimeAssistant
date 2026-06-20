import httpx
import json
import os
from typing import AsyncGenerator

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "llama3")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.8"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "1024"))

# In-memory config (can be updated at runtime)
_config = {
    "base_url": LLM_BASE_URL,
    "model": LLM_MODEL,
    "temperature": LLM_TEMPERATURE,
    "max_tokens": LLM_MAX_TOKENS,
}


def get_config() -> dict:
    return dict(_config)


def update_config(**kwargs):
    _config.update(kwargs)


def build_system_prompt(adventure_description: str, gm_role: str, characters: list[dict]) -> str:
    char_descriptions = []
    for c in characters:
        desc = (
            f"- **{c['name']}** ({c['race']} {c['char_class']}, уровень {c['level']}): "
            f"ХП {c['current_hp']}/{c['max_hp']}, КД {c['armor_class']}. "
        )
        if c.get("abilities"):
            desc += f"Способности: {c['abilities']}. "
        if c.get("background"):
            desc += f"Предыстория: {c['background']}."
        char_descriptions.append(desc)

    chars_text = "\n".join(char_descriptions)

    return f"""Ты — {gm_role}, ведущий интерактивной ролевой игры в стиле Dungeons & Dragons.

## Твоя роль
Ты ведёшь игроков через захватывающее приключение. Ты описываешь мир, управляешь NPC, создаёшь напряжение и драму. Ты НИКОГДА не выходишь из образа Мастера подземелий — ни при каких обстоятельствах.

## Описание приключения
{adventure_description}

## Персонажи игроков
{chars_text}

## Правила ведения игры
1. **Боевые ситуации**: Когда начинается бой, объявляй порядок инициативы. Броски кубиков уже рассчитываются системой — ты получаешь результаты и интерпретируешь их нарративно.
2. **Описания**: Делай описания яркими и атмосферными. Описывай звуки, запахи, ощущения.
3. **NPC**: Играй каждого NPC с уникальным голосом и мотивацией.
4. **Последствия**: Действия игроков имеют реальные последствия для мира.
5. **Баланс**: Давай игрокам шанс на успех, но не делай приключение тривиальным.
6. **Язык**: Всегда отвечай на том же языке, на котором пишут игроки.
7. **Формат**: Используй *курсив* для атмосферных описаний, **жирный** для важных моментов. Результаты бросков костей уже включены в контекст — упоминай их естественно в нарративе.

Начни с атмосферного вступления, которое погружает игроков в мир приключения."""


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
            response.raise_for_status()
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
