"""Демонстрация: загрузка персонажей из БД и небольшой бой.

Запуск:  python -m scripts.demo
"""
from __future__ import annotations

import random

from grokhanika.db import init_db, make_engine, make_session_factory, seed_all
from grokhanika.engine import Combat, Combatant, Encounter, SimpleAIController


def main() -> None:
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    with make_session_factory(engine)() as session:
        cat = seed_all(session)

        print("=== Листы персонажей (вычислено движком) ===")
        for key in ("enzo", "andryusha", "salli", "arseldor"):
            c = Combatant(cat[key], "party")
            print(
                f"{c.name:10} HP {c.current_hp:2}  физ.защ {c.phys_defense:2}  "
                f"маг.защ {c.mag_defense}  мент.защ {c.mental_defense}  "
                f"физ.атака d20+{c.phys_attack_bonus}  маг.атака d20+{c.mag_attack_bonus}"
            )

        print("\n=== Бой: партия против капитана стражи (автобой ИИ) ===")
        rng = random.Random(7)
        party = [Combatant(cat[k], "party") for k in ("andryusha", "salli", "arseldor")]
        captain = Combatant(cat["guard_captain"], "enemy")
        combat = Combat(party + [captain], rng=rng, session=session)

        encounter = Encounter(
            combat,
            controllers={"party": SimpleAIController(), "enemy": SimpleAIController()},
            max_rounds=30,
        )
        outcome = encounter.run()

        print("\n--- Лог боя ---")
        for line in outcome.log:
            print(" ", line)

        print(
            f"\nИтог: победа стороны «{outcome.winner}» за {outcome.rounds} раунд(ов) "
            f"({outcome.ended_by})"
        )
        for side, names in outcome.survivors.items():
            print(f"  выжившие [{side}]: {', '.join(names) or '—'}")


if __name__ == "__main__":
    main()
