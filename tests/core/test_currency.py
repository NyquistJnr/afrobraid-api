from app.core.currency import MINIMUM_CHARGE_MINOR_UNITS, Currency, currency_for_country


def test_currency_for_known_country():
    assert currency_for_country("DE") == Currency.EUR
    assert currency_for_country("fr") == Currency.EUR  # case-insensitive


def test_currency_for_unknown_country_defaults_to_eur():
    assert currency_for_country("US") == Currency.EUR


def test_minimum_charge_defined_for_eur():
    assert MINIMUM_CHARGE_MINOR_UNITS[Currency.EUR] == 50
