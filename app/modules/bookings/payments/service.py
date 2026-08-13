import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from arq import ArqRedis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.enums import (
    BookingStatus,
    PaymentProvider,
    PaymentPurpose,
    PaymentStatus,
    WebhookEventSource,
)
from app.modules.bookings.models import BookingPayment
from app.modules.bookings.payments import repository as payments_repo
from app.modules.bookings.tasks import (
    TASK_SEND_BOOKING_CONFIRMED_EMAIL,
    TASK_SEND_PAYMENT_NOTIFICATION,
    TASK_SEND_PAYMENT_RECEIPT_EMAIL,
)

logger = logging.getLogger("app.webhooks.stripe.payments")
paypal_logger = logging.getLogger("app.webhooks.paypal.payments")

_HANDLED_EVENT_TYPES = {"payment_intent.succeeded", "payment_intent.payment_failed"}
_HANDLED_PAYPAL_EVENT_TYPES = {"PAYMENT.CAPTURE.COMPLETED", "PAYMENT.CAPTURE.DENIED"}


def _safe_payload(event: Any) -> str:
    to_dict = getattr(event, "to_dict_recursive", None) or getattr(event, "to_dict", None)
    if to_dict is None:
        return "{}"
    try:
        return json.dumps(to_dict())
    except (TypeError, ValueError):
        return "{}"


async def finalize_payment_succeeded(
    db: AsyncSession,
    queue: ArqRedis,
    payment: BookingPayment,
    *,
    provider_order_id: str,
    provider_charge_id: str | None,
    payment_method_ref: str | None = None,
) -> None:
    """Provider-agnostic success path, shared by the Stripe webhook handler,
    the PayPal capture endpoint, and the PayPal webhook handler. Idempotent:
    a redelivered webhook that arrives after the capture endpoint (or the
    other way around) already finalized this payment is a safe no-op."""
    if payment.status == PaymentStatus.SUCCEEDED:
        return

    payment.status = PaymentStatus.SUCCEEDED
    if payment.provider == PaymentProvider.STRIPE:
        payment.stripe_payment_intent_id = provider_order_id
        payment.stripe_charge_id = provider_charge_id
    else:
        payment.paypal_order_id = provider_order_id
        payment.paypal_capture_id = provider_charge_id
    await db.flush()

    booking = await bookings_repo.get_booking_by_id(db, payment.booking_id)
    if booking is None:
        return

    was_pending = booking.status == BookingStatus.PENDING_PAYMENT
    if was_pending and payment.purpose in (PaymentPurpose.FULL, PaymentPurpose.DEPOSIT):
        booking.status = BookingStatus.CONFIRMED
        booking.confirmed_at = datetime.now(UTC)
        booking.hold_expires_at = None
        if payment.provider == PaymentProvider.STRIPE and isinstance(payment_method_ref, str):
            booking.stripe_payment_method_id = payment_method_ref
        await db.flush()

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


async def finalize_payment_failed(
    db: AsyncSession,
    payment: BookingPayment,
    *,
    failure_code: str | None,
    failure_message: str | None,
) -> None:
    if payment.status == PaymentStatus.SUCCEEDED:
        return
    payment.status = PaymentStatus.FAILED
    payment.failure_code = failure_code
    payment.failure_message = failure_message
    await db.flush()
    await db.commit()


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

    payment_method_id = getattr(intent, "payment_method", None)
    await finalize_payment_succeeded(
        db,
        queue,
        payment,
        provider_order_id=intent.id,
        provider_charge_id=getattr(intent, "latest_charge", None),
        payment_method_ref=payment_method_id if isinstance(payment_method_id, str) else None,
    )


async def _handle_payment_intent_failed(db: AsyncSession, intent: Any) -> None:
    payment = await _resolve_payment(db, intent)
    if payment is None:
        logger.warning("payment_intent.payment_failed for unknown intent %s", intent.id)
        return

    last_error = getattr(intent, "last_payment_error", None)
    await finalize_payment_failed(
        db,
        payment,
        failure_code=getattr(last_error, "code", None) if last_error else None,
        failure_message=getattr(last_error, "message", None) if last_error else None,
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
        intent = event.data.object
        if event.type == "payment_intent.succeeded":
            await _handle_payment_intent_succeeded(db, queue, intent)
        elif event.type == "payment_intent.payment_failed":
            await _handle_payment_intent_failed(db, intent)
        await payments_repo.mark_processed(db, webhook_row)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        await payments_repo.mark_failed(db, webhook_row, error=str(exc))
        await db.commit()
        raise


async def _resolve_paypal_payment(db: AsyncSession, resource: dict[str, Any]):
    order_id = (resource.get("supplementary_data") or {}).get("related_ids", {}).get("order_id")
    if order_id:
        payment = await bookings_repo.get_payment_by_paypal_order_id(db, order_id)
        if payment is not None:
            return payment

    # Fallback for a redelivery that outraces our own capture-endpoint write -
    # resolve via the booking_id:purpose we always stamp into the order's
    # custom_id at creation time (mirrors the Stripe metadata fallback above).
    custom_id = resource.get("custom_id")
    if not custom_id or ":" not in custom_id:
        return None
    booking_id_str, _, purpose_str = custom_id.partition(":")
    try:
        return await bookings_repo.get_pending_payment(
            db, uuid.UUID(booking_id_str), PaymentPurpose(purpose_str)
        )
    except ValueError:
        return None


async def _handle_paypal_capture_completed(db: AsyncSession, queue: ArqRedis, resource: dict[str, Any]) -> None:
    payment = await _resolve_paypal_payment(db, resource)
    if payment is None:
        paypal_logger.warning("PAYMENT.CAPTURE.COMPLETED for unresolved resource %s", resource.get("id"))
        return

    order_id = (resource.get("supplementary_data") or {}).get("related_ids", {}).get("order_id")
    await finalize_payment_succeeded(
        db,
        queue,
        payment,
        provider_order_id=order_id or payment.paypal_order_id or "",
        provider_charge_id=resource.get("id"),
    )


async def _handle_paypal_capture_denied(db: AsyncSession, resource: dict[str, Any]) -> None:
    payment = await _resolve_paypal_payment(db, resource)
    if payment is None:
        paypal_logger.warning("PAYMENT.CAPTURE.DENIED for unresolved resource %s", resource.get("id"))
        return

    await finalize_payment_failed(
        db,
        payment,
        failure_code="CAPTURE_DENIED",
        failure_message=resource.get("status_details", {}).get("reason"),
    )


async def handle_paypal_webhook_event(db: AsyncSession, queue: ArqRedis, *, event: dict[str, Any]) -> None:
    """Reconciliation safety net for the PayPal checkout stream - insert-first
    dedupe identical in shape to `handle_webhook_event` above. Not the
    primary success path: `service.capture_paypal_payment` finalizes the
    payment synchronously when the customer approves, so this is expected to
    find an already-SUCCEEDED payment most of the time."""
    event_id = event["id"]
    event_type = event["event_type"]

    try:
        webhook_row = await payments_repo.create_paypal_received(
            db,
            paypal_event_id=event_id,
            event_type=event_type,
            payload=json.dumps(event),
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return

    if event_type not in _HANDLED_PAYPAL_EVENT_TYPES:
        await payments_repo.mark_paypal_ignored(db, webhook_row)
        await db.commit()
        return

    try:
        resource = event.get("resource") or {}
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            await _handle_paypal_capture_completed(db, queue, resource)
        elif event_type == "PAYMENT.CAPTURE.DENIED":
            await _handle_paypal_capture_denied(db, resource)
        await payments_repo.mark_paypal_processed(db, webhook_row)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        await payments_repo.mark_paypal_failed(db, webhook_row, error=str(exc))
        await db.commit()
        raise
