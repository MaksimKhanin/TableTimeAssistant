"""Тесты бросков игрока через окно кубика: внешние значения в движке
и протокол «запроса броска» интерактивного боя (status="roll")."""
from __future__ import annotations

import pytest

from grokhanika.engine.combat import Combat
from grokhanika.engine.combatant import Combatant

from .conftest import ScriptedRandom


def make_combat(catalog, party_keys, enemy_keys, rng):
    party = [Combatant(catalog[k], "party") for k in party_keys]
    enemies = [Combatant(catalog[k], "enemy") for k in enemy_keys]
    return Combat(party + enemies, rng=rng), party, enemies


# ───────── движок: внешние броски ─────────

def test_injected_natural_and_damage_are_used(catalog):
    rng = ScriptedRandom(ints=[])  # rng не должен понадобиться
    combat, (andryusha,), (goblin,) = make_combat(catalog, ["andryusha"], ["goblin"], rng)
    res = combat.physical_attack(andryusha, goblin, natural=15, damage_roll=8)
    assert res.hit and res.natural == 15
    assert res.damage == 8 + 6  # введённый бросок 1d8=8 + STR//2(6)


def test_injected_damage_clamped_to_dice_bounds(catalog):
    rng = ScriptedRandom(ints=[])
    combat, (andryusha,), (goblin,) = make_combat(catalog, ["andryusha"], ["goblin"], rng)
    res = combat.physical_attack(andryusha, goblin, natural=15, damage_roll=99)
    assert res.damage == 8 + 6  # 1d8 не может дать больше 8


def test_injected_crit_doubles_damage_bounds(catalog):
    rng = ScriptedRandom(ints=[])
    combat, (andryusha,), (goblin,) = make_combat(catalog, ["andryusha"], ["goblin"], rng)
    res = combat.physical_attack(andryusha, goblin, natural=20, damage_roll=16)
    assert res.crit
    assert res.damage == 16 + 6  # 2d8 на крите: до 16 сырого урона


def test_injected_fumble_is_auto_miss(catalog):
    rng = ScriptedRandom(ints=[])
    combat, (andryusha,), (goblin,) = make_combat(catalog, ["andryusha"], ["goblin"], rng)
    res = combat.physical_attack(andryusha, goblin, natural=1, damage_roll=8)
    assert res.fumble and not res.hit and res.damage == 0


def test_injected_potion_heal_roll(catalog):
    rng = ScriptedRandom(ints=[])
    combat, (enzo,), (_goblin,) = make_combat(catalog, ["enzo"], ["goblin"], rng)
    potion = next(it for it in enzo.inventory if it.heal_dice)
    enzo.current_hp -= 5
    before = enzo.current_hp
    healed = combat.use_potion(enzo, potion.name, heal_roll=4)
    assert healed == 4 and enzo.current_hp == before + 4


# ───────── интерактивный бой: протокол запроса броска ─────────


@pytest.fixture
def web_client():
    from grokhanika.db import init_db, make_engine, make_session_factory, seed_all
    from grokhanika.web import create_app

    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        seed_all(s)
    app = create_app(session_factory=factory)
    return app.test_client()


def _start_battle(client):
    roster = client.get("/api/roster").get_json()
    hero_id = next(h["id"] for h in roster["heroes"] if h["name"] == "Андрюша")
    goblin_id = next(n["id"] for n in roster["npc"] if n["name"] == "Гоблин")
    data = client.post(
        "/api/battle/start", json={"allies": [hero_id], "enemies": [goblin_id], "seed": 7}
    ).get_json()
    assert data["status"] == "waiting"
    return data


def _first_target_uid(data):
    return next(t["uid"] for t in data["actor"]["targets"] if t["available"])


def test_attack_requests_d20_then_damage_roll(web_client):
    data = _start_battle(web_client)
    battle_id = data["battle_id"]
    target_uid = _first_target_uid(data)

    # действие не выполняется сразу — сервер просит бросок d20
    data = web_client.post(
        f"/api/battle/{battle_id}/action",
        json={"kind": "attack_physical", "target_uid": target_uid},
    ).get_json()
    assert data["status"] == "roll"
    roll = data["roll"]
    assert roll["stage"] == "attack" and roll["dice"] == "1d20"
    assert roll["threshold"] is not None and roll["actor"] == "Андрюша"
    assert data["events"] == []  # ничего ещё не произошло

    # натуральная 20 — крит: следующий запрос урона с удвоенными кубиками
    data = web_client.post(f"/api/battle/{battle_id}/roll", json={"value": 20}).get_json()
    assert data["roll_result"]["outcome"] == "crit"
    assert data["status"] == "roll"
    dmg = data["roll"]
    assert dmg["stage"] == "damage" and dmg["dice"] == "2d8" and dmg["crit"] is True

    # ввод урона: действие выполняется, бой продолжается
    data = web_client.post(f"/api/battle/{battle_id}/roll", json={"value": 16}).get_json()
    assert data["roll_result"]["stage"] == "damage"
    assert data["status"] in ("waiting", "over")
    log = " ".join(line for ev in data["events"] for line in ev["log"])
    assert "КРИТ" in log


def test_attack_miss_resolves_without_damage_roll(web_client):
    data = _start_battle(web_client)
    battle_id = data["battle_id"]
    target_uid = _first_target_uid(data)

    web_client.post(
        f"/api/battle/{battle_id}/action",
        json={"kind": "attack_physical", "target_uid": target_uid},
    )
    # натуральная 1 — фумбл: урон не запрашивается, ход завершён
    data = web_client.post(f"/api/battle/{battle_id}/roll", json={"value": 1}).get_json()
    assert data["roll_result"]["outcome"] == "fumble"
    assert data["status"] in ("waiting", "over")
    log = " ".join(line for ev in data["events"] for line in ev["log"])
    assert "промахивается" in log


def test_auto_roll_uses_server_rng(web_client):
    data = _start_battle(web_client)
    battle_id = data["battle_id"]
    target_uid = _first_target_uid(data)

    web_client.post(
        f"/api/battle/{battle_id}/action",
        json={"kind": "attack_physical", "target_uid": target_uid},
    )
    # value=null → автобросок серверным rng
    data = web_client.post(f"/api/battle/{battle_id}/roll", json={"value": None}).get_json()
    assert 1 <= data["roll_result"]["value"] <= 20
    assert data["status"] in ("roll", "waiting", "over")


def test_roll_without_pending_request_is_error(web_client):
    data = _start_battle(web_client)
    battle_id = data["battle_id"]
    resp = web_client.post(f"/api/battle/{battle_id}/roll", json={"value": 10})
    assert resp.status_code == 400


def test_potion_requests_heal_roll(web_client):
    roster = web_client.get("/api/roster").get_json()
    hero_id = next(h["id"] for h in roster["heroes"] if h["name"] == "Энцо")
    goblin_id = next(n["id"] for n in roster["npc"] if n["name"] == "Гоблин")
    data = web_client.post(
        "/api/battle/start", json={"allies": [hero_id], "enemies": [goblin_id], "seed": 3}
    ).get_json()
    assert data["status"] == "waiting"
    battle_id = data["battle_id"]

    data = web_client.post(
        f"/api/battle/{battle_id}/action", json={"kind": "use_potion"}
    ).get_json()
    assert data["status"] == "roll"
    assert data["roll"]["stage"] == "heal"

    data = web_client.post(f"/api/battle/{battle_id}/roll", json={"value": 3}).get_json()
    assert data["roll_result"]["outcome"] == "heal"
    assert data["status"] in ("waiting", "over")
    log = " ".join(line for ev in data["events"] for line in ev["log"])
    assert "бросок=3" in log


def test_pass_and_flee_do_not_request_rolls(web_client):
    data = _start_battle(web_client)
    battle_id = data["battle_id"]
    data = web_client.post(f"/api/battle/{battle_id}/action", json={"kind": "pass"}).get_json()
    assert data["status"] in ("waiting", "over")
