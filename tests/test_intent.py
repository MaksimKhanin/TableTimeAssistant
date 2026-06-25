"""Тесты разбора и анализа намерений игрока."""
from __future__ import annotations

from grokhanika.adventure.intent import Intent, analyze_intent, parse_intent


def test_parse_clean_json():
    raw = (
        '{"intent_type":"skill_check","requires_roll":true,"roll_type":"взлом",'
        '"combat_initiation":false,"leaves_location":false,'
        '"search_queries":["замок","дверь"]}'
    )
    intent = parse_intent(raw)
    assert intent.intent_type == "skill_check"
    assert intent.requires_roll is True
    assert intent.roll_type == "взлом"
    assert intent.search_queries == ["замок", "дверь"]


def test_parse_json_with_noise_around():
    raw = "Конечно! Вот результат:\n{\"intent_type\": \"combat\", \"combat_initiation\": true}\nГотово."
    intent = parse_intent(raw)
    assert intent.intent_type == "combat"
    assert intent.combat_initiation is True


def test_parse_unknown_type_falls_back():
    intent = parse_intent('{"intent_type":"странное"}')
    assert intent.intent_type == "dialogue"


def test_parse_garbage_is_safe_default():
    intent = parse_intent("это вообще не json")
    assert isinstance(intent, Intent)
    assert intent.intent_type == "dialogue"
    assert intent.search_queries == []


def test_string_search_queries_coerced_to_list():
    intent = parse_intent('{"search_queries":"город"}')
    assert intent.search_queries == ["город"]


def test_bool_coercion_from_strings():
    intent = parse_intent('{"requires_roll":"да","leaves_location":"true"}')
    assert intent.requires_roll is True
    assert intent.leaves_location is True


class _FakeClient:
    def __init__(self, payload: str):
        self.payload = payload
        self.calls = []

    def chat(self, messages, *, json_mode=False, temperature=None):
        self.calls.append({"json_mode": json_mode, "temperature": temperature})
        return self.payload


def test_analyze_intent_uses_json_mode():
    client = _FakeClient('{"intent_type":"movement","leaves_location":true}')
    intent = analyze_intent(client, "краткая история", "Энцо", "иду в лес")
    assert intent.intent_type == "movement"
    assert intent.leaves_location is True
    assert client.calls[0]["json_mode"] is True


def test_analyze_intent_llm_error_safe_default():
    from grokhanika.adventure.llm import LLMError

    class _Boom:
        def chat(self, *a, **k):
            raise LLMError("down")

    intent = analyze_intent(_Boom(), "", "Салли", "осмотреться вокруг")
    assert intent.intent_type == "dialogue"
    # текст уходит в поисковый запрос как фолбэк
    assert intent.search_queries and "осмотреться" in intent.search_queries[0]
