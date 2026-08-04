import enum


class BookingItemType(str, enum.Enum):
    """A line in a priced breakdown (see `app.modules.bookings.pricing`).
    Not persisted as its own DB enum in the calculator (booking_calculations
    stores only the aggregate amounts + a flat addons table) - it becomes a
    real Postgres enum column on `booking_items` from Phase 2 onward, where
    a booking's full line-by-line breakdown is snapshotted for receipts."""

    SERVICE = "SERVICE"
    VARIATION = "VARIATION"
    ADDON = "ADDON"
    TRAVEL = "TRAVEL"
    PLATFORM_FEE = "PLATFORM_FEE"
    VAT_SERVICE = "VAT_SERVICE"
    VAT_PLATFORM_FEE = "VAT_PLATFORM_FEE"


class PaymentSchedule(str, enum.Enum):
    FULL_UPFRONT = "FULL_UPFRONT"
    DEPOSIT_THEN_BALANCE = "DEPOSIT_THEN_BALANCE"
