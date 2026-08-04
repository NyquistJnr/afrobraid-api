import enum


class Currency(str, enum.Enum):
    """Only EUR is supported today - all onboarded braider countries (DE, FR,
    AT, ...) settle in euros. Kept as an enum (rather than a bare string)
    so the booking/payment tables have a real DB type to snapshot against,
    and so a second currency is a matter of adding a member, not a migration
    of every money column."""

    EUR = "EUR"


# Stripe requires a minimum charge amount per currency (in minor units) -
# https://stripe.com/docs/currencies#minimum-and-maximum-charge-amounts.
# Only the currencies we actually support need an entry.
MINIMUM_CHARGE_MINOR_UNITS: dict[Currency, int] = {
    Currency.EUR: 50,  # EUR 0.50
}

# Country (ISO 3166-1 alpha-2, as stored on BraiderServiceLocation.country)
# -> settlement currency. Every country a braider can onboard Stripe Connect
# from (see payment_setup/client.py) must have an entry here.
_COUNTRY_CURRENCY: dict[str, Currency] = {
    "DE": Currency.EUR,
    "FR": Currency.EUR,
    "AT": Currency.EUR,
    "NL": Currency.EUR,
    "BE": Currency.EUR,
    "ES": Currency.EUR,
    "IT": Currency.EUR,
    "PT": Currency.EUR,
    "IE": Currency.EUR,
    "LU": Currency.EUR,
    "FI": Currency.EUR,
    "GR": Currency.EUR,
}


def currency_for_country(country_code: str) -> Currency:
    """Resolves the settlement currency for a braider's service-location
    country. Defaults to EUR for any unmapped country rather than raising,
    since every currently supported market is euro-denominated - revisit
    this default the day a non-EUR country is onboarded."""
    return _COUNTRY_CURRENCY.get(country_code.upper(), Currency.EUR)
