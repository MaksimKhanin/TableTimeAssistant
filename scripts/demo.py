"""Демонстрация: загрузка персонажей из БД и небольшой бой.

Запуск:  python -m scripts.demo
"""
from __future__ import annotations

import random

from grokhanika.db import init_db, make_engine, make_session_factory, seed_all
from grokhanika.engine.combat import Combat
from grokhanika.engine.combatant import Combatant


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

        print("\n=== Бой: партия против некроманта ===")
        rng = random.Random(7)
        party = [Combatant(cat[k], "party") for k in ("andryusha", "salli", "arseldor")]
        necromancer = Combatant(cat["necromancer"], "enemy")
        combat = Combat(party + [necromancer], rng=rng, session=session)

        combat.fire_combat_start()  # некромант призывает гоблинов
        order = combat.roll_initiative()
        print("Инициатива:", " → ".join(c.name for c in order))

        # один раунд: каждый бьёт первого доступного врага
        for actor in order:
            if not actor.can_act:
                continue
            targets = [t for t in combat.opponents_of(actor) if not t.is_dying]
            if not targets:
                break
            combat.physical_attack(actor, targets[0])

        print("\n--- Лог боя ---")
        for line in combat.log:
            print(" ", line)


if __name__ == "__main__":
    main()
