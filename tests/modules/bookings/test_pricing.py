"""Pure-function tests for app.modules.bookings.pricing - no DB, no fixtures.
This is the highest-value test file in the booking flow: every money
invariant the rest of the system leans on (deposit + balance == total,
braider shares never exceed their charge, VAT computed per-base then
summed) is pinned down here first.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.currency import Currency
from app.core.exceptions import PricingInvariantError
from app.modules.bookings.enums import BookingItemType, PaymentSchedule
from app.modules.bookings.pricing import (
    FULL_PAYMENT_MARGIN_HOURS,
    FULL_PAYMENT_THRESHOLD_HOURS,
    PricingComponent,
    _assert_invariants,
    calculate_booking_price,
)
from app.modules.platform_settings.cache import EffectivePlatformSettings
from app.modules.platform_settings.models import SettingValueType

NOW = datetime(2026, 1, 1, tzinfo=UTC)
FAR_FUTURE = NOW + timedelta(days=30)
SOON = NOW + timedelta(hours=5)


def _settings(
    *,
    fee_type=SettingValueType.PERCENTAGE,
    fee_value=Decimal("10"),
    vat_service_type=SettingValueType.PERCENTAGE,
    vat_service_value=Decimal("20"),
    vat_fee_type=SettingValueType.PERCENTAGE,
    vat_fee_value=Decimal("20"),
    deposit_type=SettingValueType.PERCENTAGE,
    deposit_value=Decimal("10"),
) -> EffectivePlatformSettings:
    return EffectivePlatformSettings(
        platform_fee_type=fee_type,
        platform_fee_value=fee_value,
        vat_service_type=vat_service_type,
        vat_service_value=vat_service_value,
        vat_platform_fee_type=vat_fee_type,
        vat_platform_fee_value=vat_fee_value,
        deposit_type=deposit_type,
        deposit_value=deposit_value,
    )


def _service(amount: str) -> PricingComponent:
    return PricingComponent(item_type=BookingItemType.SERVICE, amount=Decimal(amount))


def test_approved_example_two_hundred_subtotal():
    # The stakeholder's own worked example: 200 subtotal -> 20 fee ->
    # 40 + 4 VAT -> 264 total, braider keeps 200.
    result = calculate_booking_price(
        service_component=_service("200.00"),
        currency=Currency.EUR,
        settings=_settings(),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    assert result.subtotal == Decimal("200.00")
    assert result.platform_fee == Decimal("20.00")
    assert result.vat_on_service == Decimal("40.00")
    assert result.vat_on_platform_fee == Decimal("4.00")
    assert result.vat_total == Decimal("44.00")
    assert result.total == Decimal("264.00")
    assert result.deposit_amount == Decimal("26.40")
    assert result.balance_amount == Decimal("237.60")
    assert result.braider_share_total == Decimal("200.00")
    assert result.braider_share_deposit == Decimal("20.00")
    assert result.braider_share_balance == Decimal("180.00")
    assert result.payment_schedule == PaymentSchedule.DEPOSIT_THEN_BALANCE


def test_variation_replaces_base_price_not_added():
    # A variation's price is an absolute replacement for base_price, never
    # additive - base 180 + variation 200 must price at 200, not 380.
    variation = PricingComponent(item_type=BookingItemType.VARIATION, amount=Decimal("200.00"))
    result = calculate_booking_price(
        service_component=variation,
        currency=Currency.EUR,
        settings=_settings(),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    assert result.service_subtotal == Decimal("200.00")
    assert result.subtotal == Decimal("200.00")


def test_optional_addons_are_additive():
    addons = [
        PricingComponent(item_type=BookingItemType.ADDON, amount=Decimal("15.00")),
        PricingComponent(item_type=BookingItemType.ADDON, amount=Decimal("5.00")),
    ]
    result = calculate_booking_price(
        service_component=_service("100.00"),
        addon_components=addons,
        currency=Currency.EUR,
        settings=_settings(),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    assert result.service_subtotal == Decimal("120.00")


def test_required_addon_flows_through_as_required():
    required = PricingComponent(
        item_type=BookingItemType.ADDON, amount=Decimal("10.00"), is_required=True
    )
    result = calculate_booking_price(
        service_component=_service("100.00"),
        addon_components=[required],
        currency=Currency.EUR,
        settings=_settings(),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    addon_lines = [line for line in result.lines if line.item_type == BookingItemType.ADDON]
    assert len(addon_lines) == 1
    assert addon_lines[0].is_required is True


def test_zero_priced_addon_allowed():
    addon = PricingComponent(item_type=BookingItemType.ADDON, amount=Decimal("0.00"))
    result = calculate_booking_price(
        service_component=_service("100.00"),
        addon_components=[addon],
        currency=Currency.EUR,
        settings=_settings(),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    assert result.service_subtotal == Decimal("100.00")


def test_travel_fee_added_only_when_component_given():
    travel = PricingComponent(item_type=BookingItemType.TRAVEL, amount=Decimal("12.50"))
    with_travel = calculate_booking_price(
        service_component=_service("100.00"),
        travel_component=travel,
        currency=Currency.EUR,
        settings=_settings(),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    without_travel = calculate_booking_price(
        service_component=_service("100.00"),
        currency=Currency.EUR,
        settings=_settings(),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    assert with_travel.subtotal == Decimal("112.50")
    assert without_travel.subtotal == Decimal("100.00")
    assert without_travel.travel_fee == Decimal("0.00")
    assert not any(line.item_type == BookingItemType.TRAVEL for line in without_travel.lines)


def test_null_travel_fee_means_free_not_an_error():
    zero_travel = PricingComponent(item_type=BookingItemType.TRAVEL, amount=Decimal("0.00"))
    result = calculate_booking_price(
        service_component=_service("100.00"),
        travel_component=zero_travel,
        currency=Currency.EUR,
        settings=_settings(),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    assert result.subtotal == Decimal("100.00")
    assert not any(line.item_type == BookingItemType.TRAVEL for line in result.lines)


def test_vat_computed_per_base_then_summed_not_blended():
    # Distinct service/fee VAT rates - if the implementation blended them
    # into "20% of (subtotal + fee)" this would still coincidentally pass
    # when rates are equal (see the approved example), so this test uses
    # different rates specifically to catch that bug.
    result = calculate_booking_price(
        service_component=_service("100.00"),
        currency=Currency.EUR,
        settings=_settings(vat_service_value=Decimal("19"), vat_fee_value=Decimal("21")),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    # subtotal 100, fee 10% -> 10.00
    assert result.platform_fee == Decimal("10.00")
    assert result.vat_on_service == Decimal("19.00")  # 19% of 100
    assert result.vat_on_platform_fee == Decimal("2.10")  # 21% of 10
    assert result.vat_total == Decimal("21.10")
    assert result.total == Decimal("131.10")


def test_divergent_vat_rates_kleinunternehmer_service_zero_percent():
    result = calculate_booking_price(
        service_component=_service("100.00"),
        currency=Currency.EUR,
        settings=_settings(vat_service_value=Decimal("0"), vat_fee_value=Decimal("19")),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    assert result.vat_on_service == Decimal("0.00")
    assert result.vat_on_platform_fee == Decimal("1.90")  # 19% of the 10.00 fee
    assert result.vat_total == Decimal("1.90")
    assert result.total == Decimal("111.90")


def test_fixed_platform_fee_type():
    result = calculate_booking_price(
        service_component=_service("100.00"),
        currency=Currency.EUR,
        settings=_settings(fee_type=SettingValueType.FIXED, fee_value=Decimal("7.50")),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    assert result.platform_fee == Decimal("7.50")


def test_fixed_deposit_type():
    result = calculate_booking_price(
        service_component=_service("500.00"),
        currency=Currency.EUR,
        settings=_settings(deposit_type=SettingValueType.FIXED, deposit_value=Decimal("30.00")),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    assert result.deposit_amount == Decimal("30.00")
    assert result.balance_amount == result.total - Decimal("30.00")


def test_deposit_clamped_to_stripe_minimum():
    # A tiny total with a 1% deposit would compute well under EUR 0.50 -
    # must be clamped up to the minimum chargeable amount.
    result = calculate_booking_price(
        service_component=_service("5.00"),
        currency=Currency.EUR,
        settings=_settings(deposit_type=SettingValueType.PERCENTAGE, deposit_value=Decimal("1")),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    assert result.deposit_amount >= Decimal("0.50")


def test_dust_balance_folds_into_full_upfront():
    # A deposit rate close to 100% leaves a balance under EUR 0.50 - must
    # fold into a single full-upfront charge rather than a second,
    # unchargeable payment.
    result = calculate_booking_price(
        service_component=_service("100.00"),
        currency=Currency.EUR,
        settings=_settings(deposit_type=SettingValueType.PERCENTAGE, deposit_value=Decimal("99.9")),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    assert result.payment_schedule == PaymentSchedule.FULL_UPFRONT
    assert result.balance_amount == Decimal("0.00")
    assert result.deposit_amount == result.total


def test_full_upfront_when_within_threshold_plus_grace():
    starts_at = NOW + timedelta(hours=FULL_PAYMENT_THRESHOLD_HOURS + FULL_PAYMENT_MARGIN_HOURS)
    result = calculate_booking_price(
        service_component=_service("200.00"),
        currency=Currency.EUR,
        settings=_settings(),
        now=NOW,
        starts_at=starts_at,
    )
    assert result.payment_schedule == PaymentSchedule.FULL_UPFRONT
    assert result.deposit_amount == result.total
    assert result.balance_amount == Decimal("0.00")


def test_deposit_path_just_past_threshold_plus_grace():
    starts_at = NOW + timedelta(
        hours=FULL_PAYMENT_THRESHOLD_HOURS + FULL_PAYMENT_MARGIN_HOURS + 1
    )
    result = calculate_booking_price(
        service_component=_service("200.00"),
        currency=Currency.EUR,
        settings=_settings(),
        now=NOW,
        starts_at=starts_at,
    )
    assert result.payment_schedule == PaymentSchedule.DEPOSIT_THEN_BALANCE


def test_indicative_quote_without_starts_at_has_no_payment_schedule():
    result = calculate_booking_price(
        service_component=_service("200.00"),
        currency=Currency.EUR,
        settings=_settings(),
        now=NOW,
    )
    assert result.payment_schedule is None
    # Still produces a usable indicative split.
    assert result.deposit_amount + result.balance_amount == result.total
    assert result.deposit_amount > Decimal("0.00")


def test_all_line_items_sum_to_total():
    addons = [
        PricingComponent(item_type=BookingItemType.ADDON, amount=Decimal("15.00")),
        PricingComponent(item_type=BookingItemType.ADDON, amount=Decimal("5.00"), is_required=True),
    ]
    travel = PricingComponent(item_type=BookingItemType.TRAVEL, amount=Decimal("8.00"))
    result = calculate_booking_price(
        service_component=_service("123.45"),
        addon_components=addons,
        travel_component=travel,
        currency=Currency.EUR,
        settings=_settings(),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    assert sum((line.amount for line in result.lines), Decimal("0.00")) == result.total


def test_half_up_rounding_not_bankers():
    # 0.125 at a rate landing exactly on a half-cent must round away from
    # zero (ROUND_HALF_UP), not to even (Python/Decimal's default context).
    result = calculate_booking_price(
        service_component=_service("2.50"),
        currency=Currency.EUR,
        settings=_settings(fee_type=SettingValueType.PERCENTAGE, fee_value=Decimal("5")),
        now=NOW,
        starts_at=FAR_FUTURE,
    )
    # 5% of 2.50 = 0.125 -> rounds to 0.13 under ROUND_HALF_UP (bankers'
    # rounding would give 0.12).
    assert result.platform_fee == Decimal("0.13")


def test_invalid_service_component_type_rejected():
    bad = PricingComponent(item_type=BookingItemType.ADDON, amount=Decimal("10.00"))
    with pytest.raises(ValueError):
        calculate_booking_price(
            service_component=bad,
            currency=Currency.EUR,
            settings=_settings(),
            now=NOW,
            starts_at=FAR_FUTURE,
        )


def test_pricing_invariant_error_raised_on_corrupt_totals():
    with pytest.raises(PricingInvariantError):
        _assert_invariants(
            lines=[],
            subtotal_minor=100,
            platform_fee_minor=10,
            vat_on_service_minor=20,
            vat_on_platform_fee_minor=2,
            vat_total_minor=22,
            total_minor=999,  # wrong on purpose - should be 132
            deposit_minor=999,
            balance_minor=0,
            braider_total_minor=100,
            share_deposit_minor=100,
            share_balance_minor=0,
        )


def test_pricing_invariant_error_on_negative_amount():
    with pytest.raises(PricingInvariantError):
        _assert_invariants(
            lines=[],
            subtotal_minor=-1,
            platform_fee_minor=0,
            vat_on_service_minor=0,
            vat_on_platform_fee_minor=0,
            vat_total_minor=0,
            total_minor=-1,
            deposit_minor=-1,
            balance_minor=0,
            braider_total_minor=-1,
            share_deposit_minor=-1,
            share_balance_minor=0,
        )


# --- Property-style checks over a spread of inputs (no hypothesis dep in
# this repo, so a deterministic sweep stands in for it). ---

_SAMPLE_AMOUNTS = ["0.01", "0.50", "1.00", "9.99", "49.99", "99.99", "123.45", "999.99", "9999.99"]
_SAMPLE_RATES = [Decimal("0"), Decimal("5"), Decimal("10"), Decimal("19"), Decimal("20"), Decimal("99.99")]


def test_deposit_plus_balance_always_equals_total_property():
    for amount in _SAMPLE_AMOUNTS:
        for deposit_rate in _SAMPLE_RATES:
            for starts_at in (SOON, FAR_FUTURE):
                result = calculate_booking_price(
                    service_component=_service(amount),
                    currency=Currency.EUR,
                    settings=_settings(deposit_value=deposit_rate),
                    now=NOW,
                    starts_at=starts_at,
                )
                assert result.deposit_amount + result.balance_amount == result.total


def test_braider_shares_sum_to_subtotal_and_never_exceed_their_charge_property():
    for amount in _SAMPLE_AMOUNTS:
        for deposit_rate in _SAMPLE_RATES:
            for fee_rate in _SAMPLE_RATES:
                result = calculate_booking_price(
                    service_component=_service(amount),
                    currency=Currency.EUR,
                    settings=_settings(fee_value=fee_rate, deposit_value=deposit_rate),
                    now=NOW,
                    starts_at=FAR_FUTURE,
                )
                assert (
                    result.braider_share_deposit + result.braider_share_balance
                    == result.braider_share_total
                )
                assert result.braider_share_deposit <= result.deposit_amount
                assert result.braider_share_balance <= result.balance_amount
