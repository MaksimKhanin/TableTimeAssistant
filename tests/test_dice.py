import random

import pytest

from grokhanika.dice import Dice, is_crit, is_fumble, roll_d20


def test_parse_and_notation():
    d = Dice.parse(" 2d4 ")
    assert (d.count, d.sides) == (2, 4)
    assert d.notation == "2d4"
    assert d.minimum == 2 and d.maximum == 8


def test_parse_rejects_unknown_die():
    with pytest.raises(ValueError):
        Dice.parse("1d7")
    with pytest.raises(ValueError):
        Dice.parse("garbage")


def test_roll_within_bounds():
    rng = random.Random(1)
    d = Dice(3, 6)
    for _ in range(200):
        v = d.roll(rng)
        assert 3 <= v <= 18


def test_crit_doubles_dice_count():
    rng = random.Random(1)
    d = Dice(1, 8)
    for _ in range(200):
        assert d.roll(rng, crit=True) <= 16  # 2 кубика d8


def test_crit_fumble_helpers():
    assert is_crit(20) and not is_crit(19)
    assert is_fumble(1) and not is_fumble(2)


def test_roll_d20_range():
    rng = random.Random(0)
    assert all(1 <= roll_d20(rng) <= 20 for _ in range(100))
