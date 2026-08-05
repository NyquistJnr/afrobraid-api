import pytest

from app.shared.geo import calculate_distance_km


def test_distance_between_identical_points_is_zero():
    assert calculate_distance_km(lat1=52.52, lon1=13.405, lat2=52.52, lon2=13.405) == 0


def test_distance_is_symmetric():
    berlin = (52.5200, 13.4050)
    munich = (48.1351, 11.5820)
    forward = calculate_distance_km(lat1=berlin[0], lon1=berlin[1], lat2=munich[0], lon2=munich[1])
    backward = calculate_distance_km(lat1=munich[0], lon1=munich[1], lat2=berlin[0], lon2=berlin[1])
    assert forward == pytest.approx(backward)


def test_distance_between_berlin_and_munich_is_roughly_correct():
    # Known great-circle distance is ~504km.
    distance = calculate_distance_km(lat1=52.5200, lon1=13.4050, lat2=48.1351, lon2=11.5820)
    assert distance == pytest.approx(504, abs=5)


def test_one_degree_of_latitude_is_roughly_111km():
    distance = calculate_distance_km(lat1=0, lon1=0, lat2=1, lon2=0)
    assert distance == pytest.approx(111.19, abs=1)


def test_accepts_decimal_inputs():
    from decimal import Decimal

    distance = calculate_distance_km(
        lat1=Decimal("52.520000"),
        lon1=Decimal("13.404999"),
        lat2=Decimal("52.520000"),
        lon2=Decimal("13.404999"),
    )
    assert distance == 0
