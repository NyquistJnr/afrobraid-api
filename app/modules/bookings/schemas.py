import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.currency import Currency
from app.modules.bookings.enums import (
    BalanceChargeState,
    BookingItemType,
    BookingStatus,
    PaymentPurpose,
    PaymentSchedule,
    PaymentStatus,
)


class BookingCreateRequest(BaseModel):
    calculation_id: uuid.UUID
    starts_at: datetime


class BookingItemResponse(BaseModel):
    id: uuid.UUID
    item_type: BookingItemType
    name_en: str | None
    name_de: str | None
    name_fr: str | None
    line_amount: Decimal
    vat_rate: Decimal | None


class BookingPaymentResponse(BaseModel):
    id: uuid.UUID
    purpose: PaymentPurpose
    status: PaymentStatus
    amount_minor: int
    braider_share_minor: int
    amount_refunded_minor: int
    amount_transferred_minor: int
    is_off_session: bool
    created_at: datetime
    updated_at: datetime


class BookingResponse(BaseModel):
    id: uuid.UUID
    reference: str
    customer_id: uuid.UUID
    braider_id: uuid.UUID
    status: BookingStatus
    
    starts_at: datetime
    ends_at: datetime
    blocked_from: datetime
    blocked_until: datetime
    braider_timezone: str

    client_address: str | None
    client_latitude: Decimal | None
    client_longitude: Decimal | None

    subtotal: Decimal
    platform_fee: Decimal
    vat_on_service: Decimal
    vat_on_platform_fee: Decimal
    vat_total: Decimal
    total: Decimal
    deposit_amount: Decimal

    payment_schedule: PaymentSchedule
    hold_expires_at: datetime | None
    cancellation_cutoff_at: datetime

    balance_charge_due_at: datetime | None
    balance_charge_state: BalanceChargeState | None

    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None
    locale: str

    items: list[BookingItemResponse]
    payments: list[BookingPaymentResponse]


class BookingIntentResponse(BaseModel):
    booking: BookingResponse
    client_secret: str | None = Field(
        default=None,
        description="Stripe PaymentIntent client_secret. Null if no payment is required right now (e.g., 0 cost, or a future flow).",
    )
