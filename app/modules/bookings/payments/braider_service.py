import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import Currency
from app.core.exceptions import InvalidBookingDateRangeError
from app.core.money import from_minor_units
from app.core.pagination import PaginationParams
from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.enums import PaymentPurpose, PaymentStatus
from app.modules.bookings.payments.schemas import (
    PaginatedPaymentsResponse,
    PaymentListItemResponse,
    PaymentStatsResponse,
)
from app.modules.braiders import repository as braiders_repo


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_to < date_from:
        raise InvalidBookingDateRangeError()


async def get_payment_stats(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    status: PaymentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PaymentStatsResponse:
    _validate_date_range(date_from, date_to)
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    if profile is None:
        zero = from_minor_units(0)
        return PaymentStatsResponse(
            total_received=zero,
            total_refunded=zero,
            net_revenue=zero,
            pending=zero,
            currency=Currency.EUR,
        )

    stats = await bookings_repo.get_payment_stats_for_braider(
        db, profile.id, status=status, date_from=date_from, date_to=date_to
    )
    total_received = from_minor_units(stats["total_received_minor"])
    total_refunded = from_minor_units(stats["total_refunded_minor"])
    return PaymentStatsResponse(
        total_received=total_received,
        total_refunded=total_refunded,
        net_revenue=total_received - total_refunded,
        pending=from_minor_units(stats["pending_minor"]),
        currency=Currency.EUR,
    )


async def list_payments(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    params: PaginationParams,
    purpose: PaymentPurpose | None = None,
    status: PaymentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PaginatedPaymentsResponse:
    _validate_date_range(date_from, date_to)
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    if profile is None:
        return PaginatedPaymentsResponse(
            items=[],
            page=params.page,
            page_size=params.page_size,
            total_items=0,
            total_pages=0,
            has_next=False,
            has_previous=False,
        )

    items, meta = await bookings_repo.list_payments_for_braider(
        db,
        profile.id,
        params=params,
        purpose=purpose,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    references = await bookings_repo.list_booking_references(db, [p.booking_id for p in items])
    responses = [
        PaymentListItemResponse(
            id=p.id,
            booking_id=p.booking_id,
            booking_reference=references.get(p.booking_id, ""),
            purpose=p.purpose,
            status=p.status,
            amount=from_minor_units(p.amount_minor),
            amount_refunded=from_minor_units(p.amount_refunded_minor),
            is_refunded=p.amount_refunded_minor > 0,
            currency=p.currency,
            created_at=p.created_at,
        )
        for p in items
    ]
    return PaginatedPaymentsResponse(
        items=responses,
        page=meta.page,
        page_size=meta.page_size,
        total_items=meta.total_items,
        total_pages=meta.total_pages,
        has_next=meta.has_next,
        has_previous=meta.has_previous,
    )
