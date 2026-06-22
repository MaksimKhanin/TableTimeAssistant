import httpx
import json
import os
import re
from typing import AsyncGenerator

import roll_directive
from prompts_config import (
    DEFAULT_SYSTEM_ADDENDUM,
    DEFAULT_TURN_REMINDER,
    NARRATION_SYSTEM_TEMPLATE,
)

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
    "use_tools": False,   # deprecated; mechanics are now decided by the utility referee
    # Second model used by referee.py for strict-JSON rules decisions (rolls,
    # HP, scene state). Empty → reuse the narration model. Keep it small/fast.
    "utility_model": "",
    "utility_temperature": 0.2,
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


# DEFAULT_SYSTEM_ADDENDUM и DEFAULT_TURN_REMINDER импортированы из prompts_config.py


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
    hp_tracking: bool = False,
) -> str:
    char_lines = []
    for c in characters:
        str_val = c.get("strength", 5)
        dex_val = c.get("dexterity", 5)
        wis_val = c.get("wisdom", 5)
        cha_val = c.get("charisma", 5)
        line = (
            f"- **{c['name']}** ({c['race']} {c['char_class']}): "
            f"ХП {c['current_hp']}/{c['max_hp']}, "
            f"СИЛ {str_val}/ЛОВ {dex_val}/МДР {wis_val}/ХАР {cha_val}, "
            f"Защита: физ {c.get('phys_defense', dex_val//2)}/маг {c.get('mag_defense', wis_val//2)}/мент {c.get('mental_defense', 5+cha_val//2)}"
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
        entry += (
            f": ХП {n['current_hp']}/{n['max_hp']}, "
            f"Защита физ {n.get('phys_defense', 2)}/маг {n.get('mag_defense', 0)}/мент {n.get('mental_defense', 5)}"
        )
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

    addendum_block = f"\n\n{system_addendum.strip()}" if system_addendum and system_addendum.strip() else ""

    # Hard constraints injected only when roll/HP mechanics are active.
    mech_lines = []
    if roll_enforcement:
        mech_lines.append(
            "Do not invent dice totals or roll outcomes. "
            "When a check is required, describe the moment and stop — "
            "the app sends a '[Roll result]' line with the actual outcome; narrate only after receiving it."
        )
    if hp_tracking:
        mech_lines.append(
            "Never write numeric HP values or compute damage yourself. "
            "The '[Party state]' block is the only source of truth for HP."
        )
    mech_lines.append("Never output engine tags like [[...]].")
    mech_block = "\n".join(mech_lines)

    base = NARRATION_SYSTEM_TEMPLATE.format(gm_role=gm_role)
    return f"""{base}{addendum_block}

{mech_block}

## Adventure
{adventure_description}

## Heroes
{chr(10).join(char_lines)}
{npc_section}"""


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

        # Surface native function calls. request_roll gates the turn; apply_hp is
        # a side-effect that can occur several times.
        emitted_roll = False
        for tc in tool_calls_collected:
            fn = tc.get("function", {}) if isinstance(tc, dict) else {}
            name = fn.get("name")
            if name not in ("request_roll", "apply_hp"):
                continue
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if name == "apply_hp":
                yield ("hp_tool", json.dumps(args))
            elif name == "request_roll" and not emitted_roll:
                yield ("roll_tool", json.dumps(args))
                emitted_roll = True
        if emitted_roll:
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


# ── Utility (non-streaming) calls for the rules referee ───────────────────────
# These run the small, low-temperature `utility_model` and return text/JSON.
# Used by referee.py to decide rolls, HP changes and scene state.

def _strip_think_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL | re.IGNORECASE).strip()


async def chat_text(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float | None = None,
    num_predict: int = 500,
    json_format: bool = False,
) -> str:
    cfg = get_config()
    url = f"{cfg['base_url']}/api/chat"
    payload = {
        "model": model or cfg.get("utility_model") or cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": cfg.get("utility_temperature", 0.2) if temperature is None else temperature,
            "num_predict": num_predict,
        },
    }
    if json_format:
        payload["format"] = "json"
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, json=payload)
        if r.status_code >= 400:
            raise RuntimeError(f"Ollama {r.status_code}: {r.text[:200]}")
        data = r.json()
    content = (data.get("message") or {}).get("content") or ""
    return _strip_think_tags(content)


async def chat_json(
    system: str,
    user: str,
    fallback: dict,
    *,
    model: str | None = None,
) -> dict:
    """Strict-JSON utility call: try format=json, then a regex {...} salvage,
    then the supplied fallback. Never raises."""
    try:
        raw = await chat_text(system, user, model=model, json_format=True)
        return json.loads(raw)
    except Exception:
        try:
            raw = await chat_text(system, user, model=model)
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception:
            pass
    return fallback


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
