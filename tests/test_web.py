"""Тесты веб-слоя: JSON-API админки и симулятора боя."""
from __future__ import annotations

import pytest

from grokhanika.db import init_db, make_engine, make_session_factory, seed_all
from grokhanika.web import create_app


@pytest.fixture
def client():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        catalog = seed_all(s)
    app = create_app(session_factory=factory)
    app.config["CATALOG_IDS"] = {k: v.id for k, v in catalog.items()}
    return app.test_client()


# ───────────────────────── витрина ─────────────────────────


def test_categories(client):
    cats = client.get("/api/categories").get_json()
    assert [c["key"] for c in cats] == ["heroes", "npc", "items", "skills", "abilities"]


def test_heroes_are_player_characters(client):
    data = client.get("/api/cards?category=heroes").get_json()
    names = {c["name"] for c in data["items"]}
    assert names == {"Энцо", "Андрюша", "Салли", "Арсельдор"}
    assert all(c["fields"]["is_player"] for c in data["items"])
    # стат-блок считается движком
    assert all("stats" in c and c["stats"]["hp"] > 0 for c in data["items"])


def test_npc_category_excludes_players(client):
    data = client.get("/api/cards?category=npc").get_json()
    for c in data["items"]:
        assert not (c["card_type"] == "character" and c["fields"].get("is_player"))
    # фильтр по существам
    creatures = client.get("/api/cards?category=npc&filter=creature").get_json()
    assert {c["name"] for c in creatures["items"]} == {"Гоблин", "Теневой убийца", "Некромант"}


def test_items_filter_and_sort_by_price(client):
    weapons = client.get(
        "/api/cards?category=items&filter=weapon&sort=price&order=asc"
    ).get_json()["items"]
    prices = [w["fields"]["price"] for w in weapons]
    assert prices == sorted(prices)
    assert all(w["card_type"] == "weapon" for w in weapons)

    other = client.get("/api/cards?category=items&filter=other").get_json()["items"]
    assert all(w["card_type"] in {"item", "spellbook", "scroll", "instrument"} for w in other)


def test_skills_category_lists_seeded_skills(client):
    skills = client.get("/api/cards?category=skills").get_json()["items"]
    names = {s["name"] for s in skills}
    assert "Навык «Магические стрелы»" in names
    assert "Навык «Песнь храбрости»" in names
    # все карточки категории — навыки, помеченные как непродаваемые и вне инвентаря
    for s in skills:
        assert s["card_type"] == "skill"
        assert s["fields"]["non_sellable"] is True
        assert s["fields"]["in_inventory"] is False


def test_skills_filter_active_passive(client):
    passive = client.get("/api/cards?category=skills&filter=passive").get_json()["items"]
    assert passive and all(s["fields"]["is_passive"] for s in passive)
    active = client.get("/api/cards?category=skills&filter=active").get_json()["items"]
    assert active and all(not s["fields"]["is_passive"] for s in active)


def test_skills_not_in_items_category(client):
    items = client.get("/api/cards?category=items").get_json()["items"]
    assert all(it["card_type"] != "skill" for it in items)


def test_hero_serialization_includes_skills(client):
    heroes = client.get("/api/cards?category=heroes").get_json()["items"]
    arseldor = next(h for h in heroes if h["name"] == "Арсельдор")
    assert "Навык «Магические стрелы»" in arseldor["fields"]["skills"]


def test_item_serializes_granted_skill(client):
    # Лютня — предмет в категории «Предметы», который даёт навык, пока в инвентаре
    items = client.get("/api/cards?category=items&filter=other").get_json()["items"]
    lute = next(i for i in items if i["name"] == "Лютня вдохновения")
    assert lute["fields"]["grants_skill"] == "Навык «Песнь храбрости»"


def test_improdor_defender_grants_bastion(client):
    # уникальный щит Андрюши даёт пассивный навык «Бастион»
    items = client.get("/api/cards?category=items&filter=other").get_json()["items"]
    shield = next(i for i in items if i["name"] == "Защитник Импродора")
    assert shield["fields"]["grants_skill"] == "Навык «Бастион»"
    assert shield["is_unique"] is True
    # сам навык — пассивный, в категории навыков
    skills = client.get("/api/cards?category=skills&filter=passive").get_json()["items"]
    assert "Навык «Бастион»" in {s["name"] for s in skills}
    # Андрюша носит уникальный щит вместо деревянного
    heroes = client.get("/api/cards?category=heroes").get_json()["items"]
    andr = next(h for h in heroes if h["name"] == "Андрюша")
    assert "Защитник Импродора" in andr["fields"]["inventory"]


def test_create_item_granting_skill(client):
    # узнаём id существующего навыка для ссылки
    skills = client.get("/api/cards?category=skills").get_json()["items"]
    skill_id = next(s["id"] for s in skills if s["name"] == "Навык «Песнь храбрости»")
    r = client.post("/api/cards", json={
        "card_type": "instrument", "name": "Флейта вдохновения",
        "grants_skill_id": skill_id, "price": 10,
    })
    assert r.status_code == 201
    assert r.get_json()["fields"]["grants_skill"] == "Навык «Песнь храбрости»"


def test_create_casting_skill(client):
    r = client.post("/api/cards", json={
        "card_type": "skill", "name": "Навык «Ледяная игла»",
        "spell_name": "Ледяная игла", "damage_dice": "2d6", "difficulty": 8,
        "attack_stat": "wisdom", "price": 9, "is_passive": False,
    })
    assert r.status_code == 201
    created = r.get_json()
    assert created["fields"]["spell_name"] == "Ледяная игла"
    assert created["fields"]["non_sellable"] is True
    skills = client.get("/api/cards?category=skills").get_json()["items"]
    assert "Навык «Ледяная игла»" in {s["name"] for s in skills}


def test_create_skill_rejects_bad_dice(client):
    r = client.post("/api/cards", json={
        "card_type": "skill", "name": "Кривой навык", "damage_dice": "3d7",
    })
    assert r.status_code == 400
    assert "damage_dice" in r.get_json()["errors"]


def test_abilities_category(client):
    abilities = client.get("/api/cards?category=abilities").get_json()["items"]
    by_name = {a["name"]: a for a in abilities}
    assert "Удар в сердце" in by_name
    assert by_name["Удар в сердце"]["owner"] == "Теневой убийца"
    assert by_name["Удар в сердце"]["chance"] == 0.25


# ───────────────────────── формы и создание ─────────────────────────


def test_forms_include_dynamic_choices(client):
    forms = client.get("/api/forms").get_json()
    char = next(f for f in forms if f["card_type"] == "character")
    weapon_field = next(f for f in char["fields"] if f["name"] == "equipped_weapon_id")
    assert weapon_field["type"] == "choice"
    assert any(ch["label"] == "Кинжал" for ch in weapon_field["choices"])


def test_create_weapon_then_visible(client):
    r = client.post("/api/cards", json={
        "card_type": "weapon", "name": "Боевой молот",
        "damage_dice": "1d12", "price": 9, "str_requirement": 7,
    })
    assert r.status_code == 201
    assert r.get_json()["name"] == "Боевой молот"
    weapons = client.get("/api/cards?category=items&filter=weapon").get_json()["items"]
    assert "Боевой молот" in {w["name"] for w in weapons}


def test_create_rejects_bad_dice(client):
    r = client.post("/api/cards", json={
        "card_type": "weapon", "name": "Кривое", "damage_dice": "2d7",
    })
    assert r.status_code == 400
    assert "damage_dice" in r.get_json()["errors"]


def test_create_required_field_missing(client):
    r = client.post("/api/cards", json={"card_type": "weapon", "damage_dice": "1d6"})
    assert r.status_code == 400
    assert r.get_json()["errors"]["name"]


def test_player_character_point_buy_enforced(client):
    r = client.post("/api/cards", json={
        "card_type": "character", "name": "Читер", "is_player": True,
        "base_strength": 20, "base_dexterity": 5, "base_wisdom": 5, "base_charisma": 5,
    })
    assert r.status_code == 400
    assert "__form__" in r.get_json()["errors"]


def test_npc_character_skips_point_buy(client):
    r = client.post("/api/cards", json={
        "card_type": "character", "name": "Босс", "is_player": False,
        "base_strength": 20, "base_dexterity": 18, "base_wisdom": 18, "base_charisma": 18,
    })
    assert r.status_code == 201


def test_create_character_with_equipment(client):
    forms = client.get("/api/forms").get_json()
    char = next(f for f in forms if f["card_type"] == "character")
    weapon_field = next(f for f in char["fields"] if f["name"] == "equipped_weapon_id")
    dagger_id = next(ch["value"] for ch in weapon_field["choices"] if ch["label"] == "Кинжал")
    r = client.post("/api/cards", json={
        "card_type": "character", "name": "Новобранец", "is_player": True,
        "base_strength": 5, "base_dexterity": 5, "base_wisdom": 5, "base_charisma": 5,
        "equipped_weapon_id": dagger_id,
    })
    assert r.status_code == 201
    assert r.get_json()["fields"]["weapon"] == "Кинжал"


def test_create_bad_reference_rejected(client):
    r = client.post("/api/cards", json={
        "card_type": "character", "name": "Призрак", "is_player": False,
        "equipped_weapon_id": 999999,
    })
    assert r.status_code == 400
    assert "equipped_weapon_id" in r.get_json()["errors"]


# ───────────────────────── симуляция ─────────────────────────


def test_simulation_runs_and_records_steps(client):
    ids = client.application.config["CATALOG_IDS"]
    r = client.post("/api/simulate", json={
        "allies": [ids["andryusha"], ids["salli"]],
        "enemies": [ids["necromancer"]],
        "seed": 7,
    })
    assert r.status_code == 200
    data = r.get_json()
    assert data["events"], "должны быть пошаговые события"
    # первый снимок: некромант призвал двух гоблинов на старте боя
    first = data["events"][0]["combatants"]
    assert sum(1 for c in first if c["name"] == "Гоблин") == 2
    # каждое событие несёт полный снимок HP всех участников
    for ev in data["events"]:
        assert all("hp" in c and "max_hp" in c for c in ev["combatants"])
    assert data["outcome"]["winner"] in {"party", "enemy", None}


def test_simulation_deterministic_with_seed(client):
    ids = client.application.config["CATALOG_IDS"]
    payload = {"allies": [ids["enzo"], ids["arseldor"]], "enemies": [ids["assassin"]], "seed": 42}
    a = client.post("/api/simulate", json=payload).get_json()
    b = client.post("/api/simulate", json=payload).get_json()
    assert a["outcome"]["log"] == b["outcome"]["log"]


def test_simulation_requires_both_sides(client):
    ids = client.application.config["CATALOG_IDS"]
    r = client.post("/api/simulate", json={"allies": [ids["enzo"]], "enemies": []})
    assert r.status_code == 400
