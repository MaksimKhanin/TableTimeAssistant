import pytest

from grokhanika.rules.validation import (
    PointBuyError,
    points_spent,
    validate_point_buy,
)

# характеристики четырёх стартовых персонажей (§15)
CHARS = {
    "enzo": (3, 12, 5, 8),
    "andryusha": (12, 5, 3, 5),
    "salli": (5, 10, 7, 3),
    "arseldor": (3, 3, 14, 5),
}


@pytest.mark.parametrize("name,stats", CHARS.items())
def test_starting_characters_are_legal(name, stats):
    report = validate_point_buy(*stats)
    assert report.valid
    assert report.spent <= 10


def test_net_points_spent():
    # Энцо: -2(STR)+7(DEX)+0(WIS)+3(CHA) = 8 (совпадает с §15)
    assert points_spent(3, 12, 5, 8) == 8
    # Салли: 0+5+2-2 = 5 (совпадает с §15)
    assert points_spent(5, 10, 7, 3) == 5


def test_overspend_rejected():
    # +11 суммарно — превышение пула в 10 очков
    with pytest.raises(PointBuyError):
        validate_point_buy(16, 5, 5, 5)
    with pytest.raises(PointBuyError):
        validate_point_buy(10, 10, 10, 5)  # +5+5+5 = 15


def test_minimum_stat_enforced():
    with pytest.raises(PointBuyError):
        validate_point_buy(0, 5, 5, 5)


def test_exactly_ten_is_valid():
    report = validate_point_buy(10, 10, 5, 5)  # +5 +5 = 10
    assert report.valid and report.spent == 10 and report.remaining == 0
