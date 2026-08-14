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


class BookingStatus(str, enum.Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"
    CANCELLED_BY_CUSTOMER = "CANCELLED_BY_CUSTOMER"
    CANCELLED_BY_BRAIDER = "CANCELLED_BY_BRAIDER"
    CANCELLED_NO_PAYMENT = "CANCELLED_NO_PAYMENT"
    EXPIRED = "EXPIRED"
    DISPUTED = "DISPUTED"


CALENDAR_BLOCKING_STATUSES = frozenset(
    {
        BookingStatus.PENDING_PAYMENT,
        BookingStatus.CONFIRMED,
        BookingStatus.IN_PROGRESS,
        BookingStatus.COMPLETED,
        BookingStatus.NO_SHOW,
        BookingStatus.DISPUTED,
    }
)


DECLINED_BOOKING_STATUSES = frozenset(
    {
        BookingStatus.CANCELLED_BY_CUSTOMER,
        BookingStatus.CANCELLED_BY_BRAIDER,
        BookingStatus.CANCELLED_NO_PAYMENT,
        BookingStatus.EXPIRED,
    }
)

UPCOMING_BOOKING_STATUSES = frozenset(
    {
        BookingStatus.CONFIRMED,
        BookingStatus.IN_PROGRESS,
    }
)


class PaymentPurpose(str, enum.Enum):
    FULL = "FULL"
    DEPOSIT = "DEPOSIT"
    BALANCE = "BALANCE"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class BalanceChargeState(str, enum.Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SCHEDULED = "SCHEDULED"
    DUE = "DUE"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"


class WebhookEventSource(str, enum.Enum):
    CONNECT = "CONNECT"
    PAYMENTS = "PAYMENTS"


class WebhookEventStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    IGNORED = "IGNORED"
