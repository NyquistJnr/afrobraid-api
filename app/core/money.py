"""Bridges this repo's two money representations.

Human/report-facing tables (bookings, booking_items, receipts, ...) store
money the way the rest of the codebase always has: `Numeric(10, 2)` mapped
to `Decimal`. Stripe-mirroring tables (booking_payments, booking_refunds,
booking_transfers, ...) store integer minor units instead, because that is
what the Stripe API actually returns and accepts, and pricing math (the
`app.modules.bookings.pricing` module) is done entirely in minor units so
that `deposit + balance == total` is a provable integer identity rather
than a hope about Decimal rounding.

`decimal.getcontext()` is thread-local and will silently NOT apply inside
`asyncio.to_thread` (which is how every Stripe SDK call in this repo is
wrapped - see `braiders/payment_setup/client.py`), so rounding mode is
always passed explicitly at the call site here, never assumed from context.
"""

from decimal import ROUND_HALF_UP, Decimal

_TWO_PLACES = Decimal("0.01")


def to_minor_units(amount: Decimal | str | int) -> int:
    """Converts a decimal currency amount (e.g. Decimal("26.40")) to integer
    minor units (2640). Quantizes to 2dp BEFORE scaling - never `int(d * 100)`,
    which is a float-precision trap for values like Decimal("2.675")."""
    quantized = Decimal(amount).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    minor = int(quantized.scaleb(2))
    if minor < 0:
        raise ValueError(f"Amount must not be negative, got {amount!r}")
    return minor


def from_minor_units(amount_minor: int) -> Decimal:
    """Converts integer minor units (2640) back to a 2dp Decimal (26.40),
    for display or for writing into a Numeric(10,2) column."""
    if amount_minor < 0:
        raise ValueError(f"Amount must not be negative, got {amount_minor!r}")
    return Decimal(amount_minor).scaleb(-2).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
