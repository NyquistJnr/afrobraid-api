import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from arq import ArqRedis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings import payouts
from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.enums import (
    BalanceChargeState,
    BookingStatus,
    PaymentPurpose,
    PaymentStatus,
    WebhookEventSource,
)
from app.modules.bookings.payments import repository as payments_repo
from app.modules.bookings.receipts import service as receipts_service
from app.modules.bookings.tasks import (
    TASK_SEND_BOOKING_CONFIRMED_EMAIL,
    TASK_SEND_DISPUTE_ADMIN_ALERT,
    TASK_SEND_PAYMENT_NOTIFICATION,
    TASK_SEND_PAYMENT_RECEIPT_EMAIL,
)

logger = logging.getLogger("app.webhooks.stripe.payments")

_HANDLED_EVENT_TYPES = {
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
    "charge.dispute.created",
}


def _safe_payload(event: Any) -> str:
    to_dict = getattr(event, "to_dict_recursive", None) or getattr(event, "to_dict", None)
    if to_dict is None:
        return "{}"
    try:
        return json.dumps(to_dict())
    except (TypeError, ValueError):
        return "{}"


async def _resolve_payment(db: AsyncSession, intent: Any):
    payment = await bookings_repo.get_payment_by_stripe_intent_id(db, intent.id)
    if payment is not None:
        return payment

    # Fallback for the case a payment row's stripe_payment_intent_id write
    # never committed (e.g. the webhook races ahead of our own request
    # transaction) - resolve by the booking_id/purpose we always stamp into
    # PaymentIntent.metadata at creation time (design correction #7).
    metadata = getattr(intent, "metadata", None) or {}
    booking_id = metadata.get("booking_id")
    purpose = metadata.get("purpose")
    if not booking_id or not purpose:
        return None
    try:
        return await bookings_repo.get_pending_payment(
            db, uuid.UUID(booking_id), PaymentPurpose(purpose)
        )
    except ValueError:
        return None


async def _handle_payment_intent_succeeded(db: AsyncSession, queue: ArqRedis, intent: Any) -> None:
    payment = await _resolve_payment(db, intent)
    if payment is None:
        logger.warning("payment_intent.succeeded for unknown intent %s", intent.id)
        return

    if payment.status == PaymentStatus.SUCCEEDED:
        return  # already processed - webhook redelivery, nothing left to do

    payment.status = PaymentStatus.SUCCEEDED
    payment.stripe_payment_intent_id = intent.id
    payment.stripe_charge_id = getattr(intent, "latest_charge", None)
    await db.flush()

    booking = await bookings_repo.get_booking_by_id(db, payment.booking_id)
    if booking is None:
        return

    was_pending = booking.status == BookingStatus.PENDING_PAYMENT
    if was_pending and payment.purpose in (PaymentPurpose.FULL, PaymentPurpose.DEPOSIT):
        booking.status = BookingStatus.CONFIRMED
        booking.confirmed_at = datetime.now(UTC)
        booking.hold_expires_at = None
        payment_method_id = getattr(intent, "payment_method", None)
        if isinstance(payment_method_id, str):
            booking.stripe_payment_method_id = payment_method_id
        await db.flush()
    elif payment.purpose == PaymentPurpose.BALANCE:
        # Covers the customer-initiated resume path (POST /{id}/pay), whose
        # on-session confirmation only completes asynchronously via this
        # webhook. The sweeper's off-session path sets this directly since
        # confirm=True there resolves synchronously (see
        # charge_booking_balance_task) - this is then just an idempotent
        # no-op for that path, since `payment.status == SUCCEEDED` already
        # returned above on any redelivery.
        booking.balance_charge_state = BalanceChargeState.SUCCEEDED
        await db.flush()

    # Same transaction as the payment's own SUCCEEDED flip, so the receipt
    # number is only consumed if this whole thing commits (design
    # correction #4).
    await receipts_service.issue_invoice_receipt(db, booking=booking, payment=payment)

    await db.commit()

    if was_pending and payment.purpose in (PaymentPurpose.FULL, PaymentPurpose.DEPOSIT):
        await queue.enqueue_job(
            TASK_SEND_BOOKING_CONFIRMED_EMAIL,
            booking_id=str(booking.id),
        )

    await queue.enqueue_job(
        TASK_SEND_PAYMENT_RECEIPT_EMAIL,
        payment_id=str(payment.id),
    )
    await queue.enqueue_job(
        TASK_SEND_PAYMENT_NOTIFICATION,
        payment_id=str(payment.id),
    )


async def _handle_payment_intent_failed(db: AsyncSession, intent: Any) -> None:
    payment = await _resolve_payment(db, intent)
    if payment is None:
        logger.warning("payment_intent.payment_failed for unknown intent %s", intent.id)
        return
    if payment.status == PaymentStatus.SUCCEEDED:
        return

    last_error = getattr(intent, "last_payment_error", None)
    payment.status = PaymentStatus.FAILED
    payment.failure_code = getattr(last_error, "code", None) if last_error else None
    payment.failure_message = getattr(last_error, "message", None) if last_error else None
    await db.flush()
    await db.commit()


async def _handle_charge_dispute_created(db: AsyncSession, queue: ArqRedis, dispute: Any) -> None:
    """Design correction #6 - disputes land 120+ days out, typically after
    the braider has already been paid. Freezes the booking's payout (stops
    release_due_payouts_cron from picking it up if it hasn't paid out yet)
    and attempts to claw back any transfer that already went out."""
    charge = getattr(dispute, "charge", None)
    charge_id = charge if isinstance(charge, str) else getattr(charge, "id", None)
    payment = await bookings_repo.get_payment_by_stripe_charge_id(db, charge_id) if charge_id else None
    if payment is None:
        logger.warning("charge.dispute.created for unknown charge %s", charge_id)
        return

    booking = await bookings_repo.get_booking_by_id(db, payment.booking_id)
    if booking is None:
        return
    if booking.stripe_dispute_id == dispute.id:
        return  # already processed this dispute - redelivered event

    booking.status = BookingStatus.DISPUTED
    booking.payouts_frozen = True
    booking.stripe_dispute_id = dispute.id
    booking.disputed_at = datetime.now(UTC)
    await db.flush()

    await payouts.reverse_transfers_for_booking(db, booking)

    await db.commit()

    await queue.enqueue_job(
        TASK_SEND_DISPUTE_ADMIN_ALERT, booking_id=str(booking.id), dispute_id=dispute.id
    )


async def handle_webhook_event(
    db: AsyncSession, queue: ArqRedis, *, event: Any, source: WebhookEventSource
) -> None:
    """Insert-first dedupe: the `stripe_webhook_events` PK on `stripe_event_id`
    makes a redelivered event a no-op IntegrityError here rather than a
    second processing pass. This stops *duplicate* delivery; it is
    deliberately not full durability (design correction #7) - a
    `reconcile_stripe_payments` sweep (Phase 7) is what recovers a webhook
    that never arrived at all."""
    try:
        webhook_row = await payments_repo.create_received(
            db,
            stripe_event_id=event.id,
            source=source,
            event_type=event.type,
            payload=_safe_payload(event),
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return

    if event.type not in _HANDLED_EVENT_TYPES:
        await payments_repo.mark_ignored(db, webhook_row)
        await db.commit()
        return

    try:
        stripe_object = event.data.object
        if event.type == "payment_intent.succeeded":
            await _handle_payment_intent_succeeded(db, queue, stripe_object)
        elif event.type == "payment_intent.payment_failed":
            await _handle_payment_intent_failed(db, stripe_object)
        elif event.type == "charge.dispute.created":
            await _handle_charge_dispute_created(db, queue, stripe_object)
        await payments_repo.mark_processed(db, webhook_row)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        await payments_repo.mark_failed(db, webhook_row, error=str(exc))
        await db.commit()
        raise
