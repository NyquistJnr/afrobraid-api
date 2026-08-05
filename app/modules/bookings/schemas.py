import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.core.currency import Currency
from app.modules.bookings.enums import (
    BookingItemType,
    BookingStatus,
    PaymentPurpose,
    PaymentSchedule,
    PaymentStatus,
)


class BookingCreateRequest(BaseModel):
    booking_calculation_id: uuid.UUID
    starts_at: datetime
    # Explicit, typed consent rather than an implicit "submitting this form
    # means you agree" - the non-refundable deposit relies on this having
    # been shown and accepted (design correction #13).
    terms_accepted: bool

    @field_validator("terms_accepted")
    @classmethod
    def _must_accept_terms(cls, value: bool) -> bool:
        if not value:
            raise ValueError("terms_accepted must be true")
        return value


class BookingItemResponse(BaseModel):
    item_type: BookingItemType
    name: str | None
    quantity: int
    unit_amount: Decimal
    line_amount: Decimal
    is_required: bool


class BookingPaymentResponse(BaseModel):
    purpose: PaymentPurpose
    status: PaymentStatus
    amount: Decimal
    currency: Currency
    client_secret: str | None = None


class BookingResponse(BaseModel):
    id: uuid.UUID
    reference: str
    status: BookingStatus
    braider_id: uuid.UUID
    style_id: uuid.UUID
    style_name: str
    duration_minutes: int
    is_mobile: bool
    client_address: str | None
    client_latitude: Decimal | None
    client_longitude: Decimal | None
    country: str
    currency: Currency
    starts_at: datetime
    ends_at: datetime
    items: list[BookingItemResponse]
    service_subtotal: Decimal
    travel_fee: Decimal
    subtotal: Decimal
    platform_fee: Decimal
    vat_on_service: Decimal
    vat_on_platform_fee: Decimal
    vat_total: Decimal
    total: Decimal
    deposit_amount: Decimal
    balance_amount: Decimal
    payment_schedule: PaymentSchedule
    cancellation_cutoff_at: datetime
    payments: list[BookingPaymentResponse]
    created_at: datetime


class BookingSummaryResponse(BaseModel):
    id: uuid.UUID
    reference: str
    status: BookingStatus
    braider_id: uuid.UUID
    style_name: str
    starts_at: datetime
    ends_at: datetime
    total: Decimal
    currency: Currency


class PaginatedBookingsResponse(BaseModel):
    items: list[BookingSummaryResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool
