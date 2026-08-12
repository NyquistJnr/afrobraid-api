import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.core.currency import Currency
from app.modules.bookings.enums import (
    BalanceChargeState,
    BookingItemType,
    BookingStatus,
    PaymentPurpose,
    PaymentSchedule,
    PaymentStatus,
)
from app.modules.bookings.models import CancelledBy


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


class BookingRescheduleRequest(BaseModel):
    starts_at: datetime


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
    braider_name: str
    customer_name: str
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
    braider_name: str
    customer_name: str
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


class AdminBookingPaymentResponse(BaseModel):
    id: uuid.UUID
    purpose: PaymentPurpose
    status: PaymentStatus
    amount: Decimal
    amount_refunded: Decimal
    braider_share: Decimal
    is_refunded: bool
    currency: Currency
    stripe_payment_intent_id: str | None
    stripe_charge_id: str | None
    is_off_session: bool
    attempt_number: int
    failure_code: str | None
    failure_message: str | None
    created_at: datetime


class AdminBookingSummaryResponse(BaseModel):
    id: uuid.UUID
    reference: str
    status: BookingStatus
    customer_id: uuid.UUID
    customer_name: str
    customer_email: str
    braider_id: uuid.UUID
    braider_user_id: uuid.UUID | None
    braider_name: str
    braider_email: str | None
    style_id: uuid.UUID
    style_name: str
    starts_at: datetime
    ends_at: datetime
    total: Decimal
    currency: Currency
    country: str
    is_mobile: bool
    payment_schedule: PaymentSchedule
    created_at: datetime


class PaginatedAdminBookingsResponse(BaseModel):
    items: list[AdminBookingSummaryResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class AdminBookingResponse(AdminBookingSummaryResponse):
    duration_minutes: int
    client_address: str | None
    client_latitude: Decimal | None
    client_longitude: Decimal | None
    service_subtotal: Decimal
    travel_fee: Decimal
    subtotal: Decimal
    platform_fee: Decimal
    vat_on_service: Decimal
    vat_on_platform_fee: Decimal
    vat_total: Decimal
    deposit_amount: Decimal
    balance_amount: Decimal
    braider_share_total: Decimal
    braider_share_deposit: Decimal
    braider_share_balance: Decimal
    cancellation_cutoff_at: datetime
    hold_expires_at: datetime | None
    balance_charge_due_at: datetime | None
    balance_charge_state: BalanceChargeState
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    cancelled_by: CancelledBy | None
    items: list[BookingItemResponse]
    payments: list[AdminBookingPaymentResponse]
    updated_at: datetime
