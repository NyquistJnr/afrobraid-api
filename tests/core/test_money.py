from decimal import Decimal

import pytest

from app.core.money import from_minor_units, to_minor_units


def test_to_minor_units_basic():
    assert to_minor_units(Decimal("26.40")) == 2640
    assert to_minor_units(Decimal("0.50")) == 50
    assert to_minor_units(Decimal("0")) == 0


def test_to_minor_units_accepts_str_and_int():
    assert to_minor_units("26.40") == 2640
    assert to_minor_units(5) == 500


def test_to_minor_units_quantizes_before_scaling_not_via_float():
    # The float trap: int(Decimal("2.675") * 100) can land on 267 due to
    # binary float imprecision if a naive `d * 100` conversion is used.
    # Quantize-then-scale must round this to the correct 2dp value first.
    assert to_minor_units(Decimal("2.675")) == 268  # ROUND_HALF_UP: 2.675 -> 2.68
    assert to_minor_units(Decimal("2.674")) == 267


def test_to_minor_units_half_up_not_bankers_rounding():
    # ROUND_HALF_UP always rounds .5 away from zero; Python's default
    # (bankers'/ROUND_HALF_EVEN) would round 0.125 -> 0.12, not 0.13.
    assert to_minor_units(Decimal("0.125")) == 13


def test_to_minor_units_rejects_negative():
    with pytest.raises(ValueError):
        to_minor_units(Decimal("-1.00"))


def test_from_minor_units_basic():
    assert from_minor_units(2640) == Decimal("26.40")
    assert from_minor_units(0) == Decimal("0.00")
    assert from_minor_units(50) == Decimal("0.50")


def test_from_minor_units_rejects_negative():
    with pytest.raises(ValueError):
        from_minor_units(-1)


def test_round_trip_is_stable_for_2dp_values():
    for value in ("0.00", "0.01", "0.50", "26.40", "264.00", "9999.99", "123.45"):
        d = Decimal(value)
        assert from_minor_units(to_minor_units(d)) == d
