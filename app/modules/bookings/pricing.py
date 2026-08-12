"""Pure pricing engine for bookings - no DB, no I/O, no side effects.

Callers resolve everything (braider style, variation, addons, travel fee,
the effective platform settings) from the DB first, then hand this module
plain `PricingComponent` inputs. All arithmetic happens in integer minor
units (see `app.core.money`) so that identities like `deposit + balance ==
total` are provable rather than hoped-for Decimal rounding, and the result
is converted back to `Decimal` only at the very end for callers that write
into `Numeric(10, 2)` columns.

VAT is charged on two independent taxable supplies - the braider's service
(`vat_service_*`) and the platform's own intermediation fee
(`vat_platform_fee_*`) - and `vat_total` is *defined* as their sum. It is
never recomputed from a blended base: with both rates equal (the seeded
default) this reproduces the same number either way, but the moment a
braider is VAT-exempt (Kleinunternehmer, SS19 UStG) only one of the two
rates changes, and the split stays correct without touching this module.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from app.core.currency import MINIMUM_CHARGE_MINOR_UNITS, Currency
from app.core.exceptions import PricingInvariantError
from app.core.money import from_minor_units, to_minor_units
from app.modules.bookings.enums import BookingItemType, PaymentSchedule
from app.modules.platform_settings.cache import EffectivePlatformSettings
from app.modules.platform_settings.models import SettingValueType


FULL_PAYMENT_THRESHOLD_HOURS = 24
FULL_PAYMENT_MARGIN_HOURS = 2

_ONE = Decimal("1")


@dataclass(frozen=True)
class PricingComponent:
    """A single priced input the caller has already resolved from the DB -
    pricing performs no lookups of its own, only arithmetic over these."""

    item_type: BookingItemType
    amount: Decimal
    is_required: bool = False
    source_style_id: uuid.UUID | None = None
    source_style_variation_id: uuid.UUID | None = None
    source_addon_id: uuid.UUID | None = None
    source_braider_style_addon_id: uuid.UUID | None = None


@dataclass(frozen=True)
class PricedLine:
    item_type: BookingItemType
    amount: Decimal
    is_required: bool = False
    vat_rate: Decimal | None = None
    source_style_id: uuid.UUID | None = None
    source_style_variation_id: uuid.UUID | None = None
    source_addon_id: uuid.UUID | None = None
    source_braider_style_addon_id: uuid.UUID | None = None


@dataclass(frozen=True)
class PricingResult:
    currency: Currency
    lines: list[PricedLine] = field(default_factory=list)

    service_subtotal: Decimal = Decimal("0.00")
    travel_fee: Decimal = Decimal("0.00")
    subtotal: Decimal = Decimal("0.00")

    platform_fee_type: SettingValueType = SettingValueType.PERCENTAGE
    platform_fee_value: Decimal = Decimal("0.00")
    platform_fee: Decimal = Decimal("0.00")

    vat_service_type: SettingValueType = SettingValueType.PERCENTAGE
    vat_service_value: Decimal = Decimal("0.00")
    vat_on_service: Decimal = Decimal("0.00")

    vat_platform_fee_type: SettingValueType = SettingValueType.PERCENTAGE
    vat_platform_fee_value: Decimal = Decimal("0.00")
    vat_on_platform_fee: Decimal = Decimal("0.00")

    vat_total: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")

    deposit_type: SettingValueType = SettingValueType.PERCENTAGE
    deposit_value: Decimal = Decimal("0.00")
    deposit_amount: Decimal = Decimal("0.00")
    balance_amount: Decimal = Decimal("0.00")
    payment_schedule: PaymentSchedule | None = None

    braider_share_total: Decimal = Decimal("0.00")
    braider_share_deposit: Decimal = Decimal("0.00")
    braider_share_balance: Decimal = Decimal("0.00")


def _percentage_of(base_minor: int, rate: Decimal) -> int:
    return int((Decimal(base_minor) * rate / 100).quantize(_ONE, rounding=ROUND_HALF_UP))


def _apply_rate(base_minor: int, value_type: SettingValueType, value: Decimal) -> int:
    if value_type == SettingValueType.PERCENTAGE:
        return _percentage_of(base_minor, value)
    return to_minor_units(value)


def _split_deposit(
    total_minor: int, settings: EffectivePlatformSettings, min_charge_minor: int
) -> tuple[int, int, PaymentSchedule]:
    raw_deposit_minor = _apply_rate(total_minor, settings.deposit_type, settings.deposit_value)
    deposit_minor = min(total_minor, max(min_charge_minor, raw_deposit_minor))
    balance_minor = total_minor - deposit_minor
    if balance_minor == 0 or balance_minor < min_charge_minor:
        return total_minor, 0, PaymentSchedule.FULL_UPFRONT
    return deposit_minor, balance_minor, PaymentSchedule.DEPOSIT_THEN_BALANCE


def calculate_booking_price(
    *,
    service_component: PricingComponent,
    addon_components: list[PricingComponent] | None = None,
    travel_component: PricingComponent | None = None,
    currency: Currency,
    settings: EffectivePlatformSettings,
    now: datetime,
    starts_at: datetime | None = None,
) -> PricingResult:
    addon_components = addon_components or []

    if service_component.item_type not in (BookingItemType.SERVICE, BookingItemType.VARIATION):
        raise ValueError("service_component must be SERVICE or VARIATION")
    for addon in addon_components:
        if addon.item_type != BookingItemType.ADDON:
            raise ValueError("addon_components must all be ADDON")
    if travel_component is not None and travel_component.item_type != BookingItemType.TRAVEL:
        raise ValueError("travel_component must be TRAVEL")

    lines: list[PricedLine] = []

    service_minor = to_minor_units(service_component.amount)
    lines.append(
        PricedLine(
            item_type=service_component.item_type,
            amount=from_minor_units(service_minor),
            source_style_id=service_component.source_style_id,
            source_style_variation_id=service_component.source_style_variation_id,
        )
    )

    addons_total_minor = 0

    for addon in sorted(addon_components, key=lambda a: not a.is_required):
        addon_minor = to_minor_units(addon.amount)
        addons_total_minor += addon_minor
        lines.append(
            PricedLine(
                item_type=BookingItemType.ADDON,
                amount=from_minor_units(addon_minor),
                is_required=addon.is_required,
                source_addon_id=addon.source_addon_id,
                source_braider_style_addon_id=addon.source_braider_style_addon_id,
            )
        )

    travel_minor = 0
    if travel_component is not None:
        travel_minor = to_minor_units(travel_component.amount)
        if travel_minor > 0:
            lines.append(PricedLine(item_type=BookingItemType.TRAVEL, amount=from_minor_units(travel_minor)))

    service_subtotal_minor = service_minor + addons_total_minor
    subtotal_minor = service_subtotal_minor + travel_minor

    platform_fee_minor = _apply_rate(
        subtotal_minor, settings.platform_fee_type, settings.platform_fee_value
    )
    lines.append(PricedLine(item_type=BookingItemType.PLATFORM_FEE, amount=from_minor_units(platform_fee_minor)))

    vat_on_service_minor = _apply_rate(
        subtotal_minor, settings.vat_service_type, settings.vat_service_value
    )
    vat_on_platform_fee_minor = _apply_rate(
        platform_fee_minor, settings.vat_platform_fee_type, settings.vat_platform_fee_value
    )
    vat_total_minor = vat_on_service_minor + vat_on_platform_fee_minor

    lines.append(
        PricedLine(
            item_type=BookingItemType.VAT_SERVICE,
            amount=from_minor_units(vat_on_service_minor),
            vat_rate=settings.vat_service_value
            if settings.vat_service_type == SettingValueType.PERCENTAGE
            else None,
        )
    )
    lines.append(
        PricedLine(
            item_type=BookingItemType.VAT_PLATFORM_FEE,
            amount=from_minor_units(vat_on_platform_fee_minor),
            vat_rate=settings.vat_platform_fee_value
            if settings.vat_platform_fee_type == SettingValueType.PERCENTAGE
            else None,
        )
    )

    total_minor = subtotal_minor + platform_fee_minor + vat_total_minor
    min_charge_minor = MINIMUM_CHARGE_MINOR_UNITS[currency]

    payment_schedule: PaymentSchedule | None
    if starts_at is not None:
        hours_out = (starts_at - now).total_seconds() / 3600
        if hours_out <= FULL_PAYMENT_THRESHOLD_HOURS + FULL_PAYMENT_MARGIN_HOURS:
            deposit_minor, balance_minor, payment_schedule = total_minor, 0, PaymentSchedule.FULL_UPFRONT
        else:
            deposit_minor, balance_minor, payment_schedule = _split_deposit(
                total_minor, settings, min_charge_minor
            )
    else:
        deposit_minor, balance_minor, _ = _split_deposit(total_minor, settings, min_charge_minor)
        payment_schedule = None

    braider_total_minor = subtotal_minor
    if total_minor == 0:
        share_deposit_minor = 0
    else:
        share_deposit_minor = int(
            (Decimal(braider_total_minor) * deposit_minor / Decimal(total_minor)).quantize(
                _ONE, rounding=ROUND_HALF_UP
            )
        )
    share_balance_minor = braider_total_minor - share_deposit_minor

    _assert_invariants(
        lines=lines,
        subtotal_minor=subtotal_minor,
        platform_fee_minor=platform_fee_minor,
        vat_on_service_minor=vat_on_service_minor,
        vat_on_platform_fee_minor=vat_on_platform_fee_minor,
        vat_total_minor=vat_total_minor,
        total_minor=total_minor,
        deposit_minor=deposit_minor,
        balance_minor=balance_minor,
        braider_total_minor=braider_total_minor,
        share_deposit_minor=share_deposit_minor,
        share_balance_minor=share_balance_minor,
    )

    return PricingResult(
        currency=currency,
        lines=lines,
        service_subtotal=from_minor_units(service_subtotal_minor),
        travel_fee=from_minor_units(travel_minor),
        subtotal=from_minor_units(subtotal_minor),
        platform_fee_type=settings.platform_fee_type,
        platform_fee_value=settings.platform_fee_value,
        platform_fee=from_minor_units(platform_fee_minor),
        vat_service_type=settings.vat_service_type,
        vat_service_value=settings.vat_service_value,
        vat_on_service=from_minor_units(vat_on_service_minor),
        vat_platform_fee_type=settings.vat_platform_fee_type,
        vat_platform_fee_value=settings.vat_platform_fee_value,
        vat_on_platform_fee=from_minor_units(vat_on_platform_fee_minor),
        vat_total=from_minor_units(vat_total_minor),
        total=from_minor_units(total_minor),
        deposit_type=settings.deposit_type,
        deposit_value=settings.deposit_value,
        deposit_amount=from_minor_units(deposit_minor),
        balance_amount=from_minor_units(balance_minor),
        payment_schedule=payment_schedule,
        braider_share_total=from_minor_units(braider_total_minor),
        braider_share_deposit=from_minor_units(share_deposit_minor),
        braider_share_balance=from_minor_units(share_balance_minor),
    )


def _assert_invariants(
    *,
    lines: list[PricedLine],
    subtotal_minor: int,
    platform_fee_minor: int,
    vat_on_service_minor: int,
    vat_on_platform_fee_minor: int,
    vat_total_minor: int,
    total_minor: int,
    deposit_minor: int,
    balance_minor: int,
    braider_total_minor: int,
    share_deposit_minor: int,
    share_balance_minor: int,
) -> None:
    all_amounts = [
        subtotal_minor,
        platform_fee_minor,
        vat_on_service_minor,
        vat_on_platform_fee_minor,
        vat_total_minor,
        total_minor,
        deposit_minor,
        balance_minor,
        share_deposit_minor,
        share_balance_minor,
    ]
    if any(amount < 0 for amount in all_amounts):
        raise PricingInvariantError()
    if subtotal_minor + platform_fee_minor + vat_total_minor != total_minor:
        raise PricingInvariantError()
    if vat_on_service_minor + vat_on_platform_fee_minor != vat_total_minor:
        raise PricingInvariantError()
    if deposit_minor + balance_minor != total_minor:
        raise PricingInvariantError()
    if share_deposit_minor + share_balance_minor != braider_total_minor:
        raise PricingInvariantError()
    if share_deposit_minor > deposit_minor or share_balance_minor > balance_minor:
        raise PricingInvariantError()
    line_sum = sum(to_minor_units(line.amount) for line in lines)
    if line_sum != total_minor:
        raise PricingInvariantError()
