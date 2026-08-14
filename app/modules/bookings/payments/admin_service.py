import uuid
from datetime import date

from arq import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import Currency
from app.core.exceptions import BookingNotFoundError, InvalidBookingDateRangeError, WebhookEventNotFoundError
from app.core.money import from_minor_units
from app.core.pagination import PaginationParams
from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.enums import PaymentPurpose, PaymentStatus
from app.modules.bookings.models import Booking, BookingPayment
from app.modules.bookings.payments import repository as payments_repo
from app.modules.bookings.payments import service as payments_service
from app.modules.bookings.payments.schemas import (
    AdminPaymentListItemResponse,
    PaginatedAdminPaymentsResponse,
    ReconcileBookingResponse,
    WebhookEventRetryResponse,
)
from app.modules.braiders import repository as braiders_repo
from app.modules.users import repository as users_repo


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_to < date_from:
        raise InvalidBookingDateRangeError()


def _to_admin_payment_item(
    payment: BookingPayment,
    *,
    booking: Booking,
    customer_info: dict[uuid.UUID, dict[str, str]],
    braider_info: dict[uuid.UUID, dict[str, str | uuid.UUID]],
) -> AdminPaymentListItemResponse:
    customer = customer_info.get(booking.customer_id, {})
    braider = braider_info.get(booking.braider_id, {})
    return AdminPaymentListItemResponse(
        id=payment.id,
        booking_id=payment.booking_id,
        booking_reference=booking.reference,
        customer_id=booking.customer_id,
        customer_name=str(customer.get("name", "")),
        customer_email=str(customer.get("email", "")),
        braider_id=booking.braider_id,
        braider_user_id=braider.get("user_id") if isinstance(braider.get("user_id"), uuid.UUID) else None,
        braider_name=str(braider.get("name", "")),
        braider_email=str(braider.get("email", "")) if braider.get("email") is not None else None,
        purpose=payment.purpose,
        status=payment.status,
        amount=from_minor_units(payment.amount_minor),
        amount_refunded=from_minor_units(payment.amount_refunded_minor),
        braider_share=from_minor_units(payment.braider_share_minor),
        is_refunded=payment.amount_refunded_minor > 0,
        currency=payment.currency,
        stripe_payment_intent_id=payment.stripe_payment_intent_id,
        stripe_charge_id=payment.stripe_charge_id,
        is_off_session=payment.is_off_session,
        attempt_number=payment.attempt_number,
        failure_code=payment.failure_code,
        failure_message=payment.failure_message,
        created_at=payment.created_at,
    )


async def list_admin_payments(
    db: AsyncSession,
    *,
    params: PaginationParams,
    purpose: PaymentPurpose | None = None,
    status: PaymentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    booking_date_from: date | None = None,
    booking_date_to: date | None = None,
    customer_id: uuid.UUID | None = None,
    braider_id: uuid.UUID | None = None,
    booking_id: uuid.UUID | None = None,
    currency: Currency | None = None,
    is_refunded: bool | None = None,
    search: str | None = None,
) -> PaginatedAdminPaymentsResponse:
    _validate_date_range(date_from, date_to)
    _validate_date_range(booking_date_from, booking_date_to)
    items, meta = await bookings_repo.list_payments_for_admin(
        db,
        params=params,
        purpose=purpose,
        status=status,
        date_from=date_from,
        date_to=date_to,
        booking_date_from=booking_date_from,
        booking_date_to=booking_date_to,
        customer_id=customer_id,
        braider_id=braider_id,
        booking_id=booking_id,
        currency=currency,
        is_refunded=is_refunded,
        search=search,
    )
    bookings = await bookings_repo.list_bookings_by_ids(db, [p.booking_id for p in items])
    customer_info = await users_repo.list_admin_user_info(
        db, [booking.customer_id for booking in bookings.values()]
    )
    braider_info = await braiders_repo.list_admin_display_info(
        db, [booking.braider_id for booking in bookings.values()]
    )
    return PaginatedAdminPaymentsResponse(
        items=[
            _to_admin_payment_item(
                p,
                booking=bookings[p.booking_id],
                customer_info=customer_info,
                braider_info=braider_info,
            )
            for p in items
            if p.booking_id in bookings
        ],
        page=meta.page,
        page_size=meta.page_size,
        total_items=meta.total_items,
        total_pages=meta.total_pages,
        has_next=meta.has_next,
        has_previous=meta.has_previous,
    )


async def retry_webhook_event(
    db: AsyncSession, queue: ArqRedis, *, stripe_event_id: str
) -> WebhookEventRetryResponse:
    """Admin-triggered version of retry_webhook_events_cron's per-event
    action - ignores the stuck-age/attempts-cap thresholds since an admin
    explicitly asked for this one right now."""
    webhook_row = await payments_repo.get_by_event_id(db, stripe_event_id)
    if webhook_row is None:
        raise WebhookEventNotFoundError()
    await payments_service.reprocess_webhook_event(db, queue, webhook_row)
    return WebhookEventRetryResponse(stripe_event_id=webhook_row.stripe_event_id, status=webhook_row.status.value)


async def reconcile_booking_payments(
    db: AsyncSession, queue: ArqRedis, *, booking_id: uuid.UUID
) -> ReconcileBookingResponse:
    """Admin-triggered version of reconcile_stripe_payments_cron's
    per-payment action, scoped to one booking - ignores the age threshold
    since an admin explicitly asked for this right now."""
    booking = await bookings_repo.get_booking_by_id(db, booking_id)
    if booking is None:
        raise BookingNotFoundError()
    pending = await bookings_repo.list_pending_payments_for_booking(db, booking_id)
    for payment in pending:
        await payments_service.reconcile_pending_payment(db, queue, payment)
    return ReconcileBookingResponse(booking_id=booking_id, payments_checked=len(pending))
