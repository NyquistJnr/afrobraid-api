import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.core.currency import Currency
from app.modules.bookings.enums import PaymentPurpose, PaymentStatus


class PaymentStatsResponse(BaseModel):
    """Money-flow summary for a braider. `net_revenue` is
    total_received - total_refunded, computed regardless of any `status`
    filter applied to the request."""

    total_received: Decimal
    total_refunded: Decimal
    net_revenue: Decimal
    pending: Decimal
    currency: Currency


class PaymentListItemResponse(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    booking_reference: str
    purpose: PaymentPurpose
    status: PaymentStatus
    amount: Decimal
    amount_refunded: Decimal
    is_refunded: bool
    currency: Currency
    created_at: datetime


class PaginatedPaymentsResponse(BaseModel):
    items: list[PaymentListItemResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool
