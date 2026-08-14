import logging
import uuid
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.money import from_minor_units, to_minor_units
from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.enums import BalanceChargeState, BookingStatus, PaymentPurpose, PaymentStatus
from app.modules.bookings.models import CancelledBy
from app.modules.bookings.payments import client as payments_client
from app.modules.braiders import repository as braiders_repo
from app.modules.notifications import service as notifications_service
from app.modules.notifications.models import NotificationType
from app.modules.styles import repository as styles_repo
from app.modules.users import repository as users_repo
from app.shared.email.client import send_email
from app.shared.email.templates.booking_email import (
    render_balance_payment_failed_email,
    render_booking_cancelled_no_payment_email,
    render_booking_confirmed_email,
    render_booking_rescheduled_email,
)
from app.shared.email.templates.receipt_email import render_payment_receipt_email
from app.shared.links import build_braider_frontend_url, build_customer_frontend_url

logger = logging.getLogger("app.tasks.bookings")
settings = get_settings()

TASK_SEND_BOOKING_CONFIRMED_EMAIL = "send_booking_confirmed_email_task"
TASK_SEND_PAYMENT_RECEIPT_EMAIL = "send_payment_receipt_email_task"
TASK_SEND_PAYMENT_NOTIFICATION = "send_payment_notification_task"
TASK_SEND_BOOKING_RESCHEDULED_EMAIL = "send_booking_rescheduled_email_task"
TASK_SEND_BOOKING_RESCHEDULED_NOTIFICATION = "send_booking_rescheduled_notification_task"
TASK_CHARGE_BOOKING_BALANCE = "charge_booking_balance_task"
TASK_SEND_BALANCE_PAYMENT_FAILED_EMAIL = "send_balance_payment_failed_email_task"
TASK_SEND_BOOKING_CANCELLED_NO_PAYMENT_EMAIL = "send_booking_cancelled_no_payment_email_task"

_PAYMENT_NOTIFICATION = {
    PaymentPurpose.DEPOSIT: (
        NotificationType.PAYMENT_DEPOSIT_SUCCEEDED,
        "notifications.payment_deposit_succeeded_title",
        "notifications.payment_deposit_succeeded_body",
    ),
    PaymentPurpose.FULL: (
        NotificationType.PAYMENT_FULL_SUCCEEDED,
        "notifications.payment_full_succeeded_title",
        "notifications.payment_full_succeeded_body",
    ),
    PaymentPurpose.BALANCE: (
        NotificationType.PAYMENT_BALANCE_SUCCEEDED,
        "notifications.payment_balance_succeeded_title",
        "notifications.payment_balance_succeeded_body",
    ),
}


async def send_booking_confirmed_email_task(ctx: dict, *, booking_id: str) -> None:
    async with AsyncSessionLocal() as db:
        booking = await bookings_repo.get_booking_by_id(db, uuid.UUID(booking_id))
        if booking is None:
            logger.warning("Booking %s not found for confirmation email", booking_id)
            return

        customer = await users_repo.get_user_by_id(db, booking.customer_id)
        style = await styles_repo.get_style_by_id(db, booking.style_id)
        braider_profile = await braiders_repo.get_profile_by_id(db, booking.braider_id)
        if customer is None:
            return

        style_name = (style.name_en if style else None) or "your appointment"
        braider_name = (braider_profile.business_name if braider_profile else None) or "your braider"

        subject, html = render_booking_confirmed_email(
            first_name=customer.first_name,
            reference=booking.reference,
            style_name=style_name,
            braider_name=braider_name,
            starts_at=booking.starts_at,
            total=booking.total,
            currency=booking.currency.value,
            locale=booking.locale,
        )
        await send_email(to=customer.email, subject=subject, html=html)
        logger.info("Sent booking confirmation email for %s to %s", booking.reference, customer.email)


async def send_payment_receipt_email_task(ctx: dict, *, payment_id: str) -> None:
    async with AsyncSessionLocal() as db:
        payment = await bookings_repo.get_payment_by_id(db, uuid.UUID(payment_id))
        if payment is None:
            logger.warning("Payment %s not found for receipt email", payment_id)
            return

        booking = await bookings_repo.get_booking_by_id(db, payment.booking_id)
        if booking is None:
            logger.warning("Booking %s not found for receipt email", payment.booking_id)
            return

        customer = await users_repo.get_user_by_id(db, booking.customer_id)
        style = await styles_repo.get_style_by_id(db, booking.style_id)
        braider_profile = await braiders_repo.get_profile_by_id(db, booking.braider_id)
        if customer is None:
            return

        style_name = (style.name_en if style else None) or "your appointment"
        braider_name = (braider_profile.business_name if braider_profile else None) or "your braider"

        subject, html = render_payment_receipt_email(
            first_name=customer.first_name,
            reference=booking.reference,
            style_name=style_name,
            braider_name=braider_name,
            starts_at=booking.starts_at,
            purpose=payment.purpose,
            amount_paid=from_minor_units(payment.amount_minor),
            total=booking.total,
            balance_amount=booking.balance_amount,
            currency=payment.currency.value,
            paid_at=payment.updated_at,
            locale=booking.locale,
        )
        await send_email(to=customer.email, subject=subject, html=html)
        logger.info("Sent payment receipt email for %s (%s) to %s", booking.reference, payment.purpose, customer.email)


async def send_payment_notification_task(ctx: dict, *, payment_id: str) -> None:
    """Deliberately its own job, separate from send_payment_receipt_email_task -
    a Resend outage/retry storm on the email side must never hold up this
    notification, which only touches the DB and the websocket."""
    async with AsyncSessionLocal() as db:
        payment = await bookings_repo.get_payment_by_id(db, uuid.UUID(payment_id))
        if payment is None:
            logger.warning("Payment %s not found for payment notification", payment_id)
            return

        booking = await bookings_repo.get_booking_by_id(db, payment.booking_id)
        if booking is None:
            logger.warning("Booking %s not found for payment notification", payment.booking_id)
            return

        customer = await users_repo.get_user_by_id(db, booking.customer_id)
        if customer is None:
            return

        notification_type, title_key, body_key = _PAYMENT_NOTIFICATION[payment.purpose]
        body_params = {
            "amount": str(from_minor_units(payment.amount_minor)),
            "currency": payment.currency.value,
            "balance_amount": str(booking.balance_amount),
            "link": build_customer_frontend_url(locale=booking.locale, path=f"bookings/{booking.id}"),
        }
        notification = await notifications_service.create(
            db,
            user_id=customer.id,
            type=notification_type,
            title_key=title_key,
            body_key=body_key,
            body_params=body_params,
            related_type="booking",
            related_id=booking.id,
        )
        await db.commit()
        await db.refresh(notification)
        await notifications_service.publish_realtime(notification, locale=booking.locale)
        logger.info("Sent payment notification for %s (%s) to %s", booking.reference, payment.purpose, customer.id)


async def send_booking_rescheduled_email_task(
    ctx: dict, *, booking_id: str, old_starts_at: str
) -> None:
    async with AsyncSessionLocal() as db:
        booking = await bookings_repo.get_booking_by_id(db, uuid.UUID(booking_id))
        if booking is None:
            logger.warning("Booking %s not found for reschedule email", booking_id)
            return

        customer = await users_repo.get_user_by_id(db, booking.customer_id)
        style = await styles_repo.get_style_by_id(db, booking.style_id)
        braider_profile = await braiders_repo.get_profile_by_id(db, booking.braider_id)
        if customer is None:
            return

        style_name = (style.name_en if style else None) or "your appointment"
        braider_name = (braider_profile.business_name if braider_profile else None) or "your braider"

        subject, html = render_booking_rescheduled_email(
            first_name=customer.first_name,
            reference=booking.reference,
            style_name=style_name,
            braider_name=braider_name,
            old_starts_at=datetime.fromisoformat(old_starts_at),
            new_starts_at=booking.starts_at,
            locale=booking.locale,
        )
        await send_email(to=customer.email, subject=subject, html=html)
        logger.info("Sent booking reschedule email for %s to %s", booking.reference, customer.email)


async def send_booking_rescheduled_notification_task(ctx: dict, *, booking_id: str) -> None:
    async with AsyncSessionLocal() as db:
        booking = await bookings_repo.get_booking_by_id(db, uuid.UUID(booking_id))
        if booking is None:
            logger.warning("Booking %s not found for reschedule notification", booking_id)
            return

        braider_profile = await braiders_repo.get_profile_by_id(db, booking.braider_id)
        customer_notification = await notifications_service.create(
            db,
            user_id=booking.customer_id,
            type=NotificationType.BOOKING_RESCHEDULED,
            title_key="notifications.booking_rescheduled_customer_title",
            body_key="notifications.booking_rescheduled_customer_body",
            body_params={
                "link": build_customer_frontend_url(locale=booking.locale, path=f"bookings/{booking.id}")
            },
            related_type="booking",
            related_id=booking.id,
        )

        braider_notification = None
        if braider_profile is not None:
            braider_notification = await notifications_service.create(
                db,
                user_id=braider_profile.user_id,
                type=NotificationType.BOOKING_RESCHEDULED,
                title_key="notifications.booking_rescheduled_braider_title",
                body_key="notifications.booking_rescheduled_braider_body",
                body_params={
                    "link": build_braider_frontend_url(locale=booking.locale, path=f"bookings/{booking.id}")
                },
                related_type="booking",
                related_id=booking.id,
            )

        await db.commit()
        await db.refresh(customer_notification)
        await notifications_service.publish_realtime(customer_notification, locale=booking.locale)
        if braider_notification is not None:
            await db.refresh(braider_notification)
            await notifications_service.publish_realtime(braider_notification, locale=booking.locale)
        logger.info("Sent reschedule notification for %s", booking.reference)


def _next_balance_retry_at(*, now: datetime, starts_at: datetime, attempt_number: int) -> datetime | None:
    """`attempt_number` is the attempt that just failed (1-indexed against
    `booking_balance_retry_offsets_hours`, e.g. [2, 6, 12]). Returns the
    next `balance_charge_due_at`, or None if the ladder is exhausted or the
    next slot would land past the hard deadline - either means
    CANCELLED_NO_PAYMENT. The hard-deadline check exists so a retry can't
    be scheduled with no realistic time left to react (design correction
    #3 extended one step further)."""
    offsets = settings.booking_balance_retry_offsets_hours
    if attempt_number > len(offsets):
        return None
    candidate = now + timedelta(hours=offsets[attempt_number - 1])
    hard_deadline = starts_at - timedelta(hours=settings.booking_balance_hard_deadline_hours_before_start)
    if candidate >= hard_deadline:
        return None
    return candidate


async def _handle_balance_charge_failure(
    ctx: dict,
    db,
    booking,
    *,
    attempt_number: int,
    transfer_group: str,
    idempotency_key: str,
    failure_code: str | None,
    failure_message: str,
) -> None:
    truncated_message = failure_message[:500]
    payment = await bookings_repo.create_payment(
        db,
        booking_id=booking.id,
        purpose=PaymentPurpose.BALANCE,
        amount_minor=to_minor_units(booking.balance_amount),
        currency=booking.currency,
        braider_share_minor=to_minor_units(booking.braider_share_balance),
        stripe_payment_intent_id=None,
        idempotency_key=idempotency_key,
        is_off_session=True,
        transfer_group=transfer_group,
        attempt_number=attempt_number,
    )
    payment.status = PaymentStatus.FAILED
    payment.failure_code = failure_code
    payment.failure_message = truncated_message

    now = datetime.now(UTC)
    booking.balance_charge_attempts = attempt_number
    booking.balance_charge_last_error = truncated_message

    next_due_at = _next_balance_retry_at(now=now, starts_at=booking.starts_at, attempt_number=attempt_number)
    cancelled = next_due_at is None
    if cancelled:
        booking.balance_charge_state = BalanceChargeState.ABANDONED
        booking.status = BookingStatus.CANCELLED_NO_PAYMENT
        booking.cancelled_at = now
        booking.cancelled_by = CancelledBy.SYSTEM
    else:
        booking.balance_charge_due_at = next_due_at
        booking.balance_charge_state = BalanceChargeState.SCHEDULED

    await db.commit()

    if cancelled:
        await ctx["redis"].enqueue_job(
            TASK_SEND_BOOKING_CANCELLED_NO_PAYMENT_EMAIL, booking_id=str(booking.id)
        )
    else:
        await ctx["redis"].enqueue_job(
            TASK_SEND_BALANCE_PAYMENT_FAILED_EMAIL,
            booking_id=str(booking.id),
            failure_code=failure_code or "",
            failure_message=truncated_message,
        )
    logger.warning(
        "Balance charge attempt %d failed for booking %s (%s): %s",
        attempt_number,
        booking.reference,
        failure_code,
        truncated_message,
    )


async def charge_booking_balance_task(ctx: dict, *, booking_id: str) -> None:
    """Off-session-charges the remaining balance for a booking whose
    balance_charge_due_at has passed (enqueued by sweep_balance_charges_cron,
    which already claimed SCHEDULED -> DUE). Re-asserts CONFIRMED/DUE under
    FOR UPDATE before touching Stripe - a booking cancelled or rescheduled
    between the sweep and this task running must not get charged. CardError
    raises synchronously (design correction #13), so success/failure is
    known immediately - no webhook round-trip is required for the sweep
    path (the webhook remains a safety net; see payments/service.py)."""
    bid = uuid.UUID(booking_id)

    async with AsyncSessionLocal() as db:
        booking = await bookings_repo.get_booking_by_id_for_update(db, bid)
        if (
            booking is None
            or booking.status != BookingStatus.CONFIRMED
            or booking.balance_charge_state != BalanceChargeState.DUE
        ):
            await db.rollback()
            return
        booking.balance_charge_state = BalanceChargeState.IN_PROGRESS
        await db.commit()

    async with AsyncSessionLocal() as db:
        booking = await bookings_repo.get_booking_by_id(db, bid)
        if booking is None:
            return
        attempt_number = booking.balance_charge_attempts + 1
        idempotency_key = f"booking:{booking.id}:balance:{attempt_number}"
        transfer_group = f"booking_{booking.id}"

        try:
            intent = await payments_client.charge_off_session(
                amount_minor=to_minor_units(booking.balance_amount),
                currency=booking.currency.value,
                customer_id=booking.stripe_customer_id,
                payment_method_id=booking.stripe_payment_method_id,
                metadata={"booking_id": str(booking.id), "purpose": PaymentPurpose.BALANCE.value},
                idempotency_key=idempotency_key,
            )
        except payments_client.StripeCardError as exc:
            await _handle_balance_charge_failure(
                ctx,
                db,
                booking,
                attempt_number=attempt_number,
                transfer_group=transfer_group,
                idempotency_key=idempotency_key,
                failure_code=exc.code,
                failure_message=exc.message,
            )
            return
        except payments_client.StripeApiError as exc:
            await _handle_balance_charge_failure(
                ctx,
                db,
                booking,
                attempt_number=attempt_number,
                transfer_group=transfer_group,
                idempotency_key=idempotency_key,
                failure_code=None,
                failure_message=str(exc),
            )
            return

        payment = await bookings_repo.create_payment(
            db,
            booking_id=booking.id,
            purpose=PaymentPurpose.BALANCE,
            amount_minor=to_minor_units(booking.balance_amount),
            currency=booking.currency,
            braider_share_minor=to_minor_units(booking.braider_share_balance),
            stripe_payment_intent_id=intent.id,
            idempotency_key=idempotency_key,
            is_off_session=True,
            transfer_group=transfer_group,
            attempt_number=attempt_number,
        )
        payment.status = PaymentStatus.SUCCEEDED
        booking.balance_charge_state = BalanceChargeState.SUCCEEDED
        booking.balance_charge_attempts = attempt_number
        await db.commit()
        payment_id = str(payment.id)
        reference = booking.reference

    await ctx["redis"].enqueue_job(TASK_SEND_PAYMENT_RECEIPT_EMAIL, payment_id=payment_id)
    await ctx["redis"].enqueue_job(TASK_SEND_PAYMENT_NOTIFICATION, payment_id=payment_id)
    logger.info("Charged balance for booking %s (attempt %d)", reference, attempt_number)


async def send_balance_payment_failed_email_task(
    ctx: dict, *, booking_id: str, failure_code: str, failure_message: str
) -> None:
    async with AsyncSessionLocal() as db:
        booking = await bookings_repo.get_booking_by_id(db, uuid.UUID(booking_id))
        if booking is None:
            logger.warning("Booking %s not found for balance payment failed email", booking_id)
            return

        customer = await users_repo.get_user_by_id(db, booking.customer_id)
        style = await styles_repo.get_style_by_id(db, booking.style_id)
        braider_profile = await braiders_repo.get_profile_by_id(db, booking.braider_id)
        if customer is None:
            return

        style_name = (style.name_en if style else None) or "your appointment"
        braider_name = (braider_profile.business_name if braider_profile else None) or "your braider"
        needs_action = failure_code == "authentication_required"
        reason = failure_message or "the payment was declined"
        pay_url = build_customer_frontend_url(locale=booking.locale, path=f"bookings/{booking.id}")

        subject, html = render_balance_payment_failed_email(
            first_name=customer.first_name,
            reference=booking.reference,
            style_name=style_name,
            braider_name=braider_name,
            starts_at=booking.starts_at,
            amount=booking.balance_amount,
            currency=booking.currency.value,
            reason=reason,
            needs_action=needs_action,
            pay_url=pay_url,
            locale=booking.locale,
        )
        await send_email(to=customer.email, subject=subject, html=html)

        notification = await notifications_service.create(
            db,
            user_id=customer.id,
            type=NotificationType.PAYMENT_BALANCE_FAILED,
            title_key="notifications.payment_balance_failed_title",
            body_key="notifications.payment_balance_failed_body",
            body_params={
                "amount": str(booking.balance_amount),
                "currency": booking.currency.value,
                "reason": reason,
                "link": pay_url,
            },
            related_type="booking",
            related_id=booking.id,
        )
        await db.commit()
        await db.refresh(notification)
        await notifications_service.publish_realtime(notification, locale=booking.locale)
        logger.info("Sent balance payment failed email for %s to %s", booking.reference, customer.email)


async def send_booking_cancelled_no_payment_email_task(ctx: dict, *, booking_id: str) -> None:
    async with AsyncSessionLocal() as db:
        booking = await bookings_repo.get_booking_by_id(db, uuid.UUID(booking_id))
        if booking is None:
            logger.warning("Booking %s not found for cancelled-no-payment email", booking_id)
            return

        customer = await users_repo.get_user_by_id(db, booking.customer_id)
        style = await styles_repo.get_style_by_id(db, booking.style_id)
        braider_profile = await braiders_repo.get_profile_by_id(db, booking.braider_id)
        if customer is None:
            return

        style_name = (style.name_en if style else None) or "your appointment"
        braider_name = (braider_profile.business_name if braider_profile else None) or "your braider"
        link = build_customer_frontend_url(locale=booking.locale, path=f"bookings/{booking.id}")

        subject, html = render_booking_cancelled_no_payment_email(
            first_name=customer.first_name,
            reference=booking.reference,
            style_name=style_name,
            braider_name=braider_name,
            starts_at=booking.starts_at,
            locale=booking.locale,
        )
        await send_email(to=customer.email, subject=subject, html=html)

        notification = await notifications_service.create(
            db,
            user_id=customer.id,
            type=NotificationType.BOOKING_CANCELLED_NO_PAYMENT,
            title_key="notifications.booking_cancelled_no_payment_title",
            body_key="notifications.booking_cancelled_no_payment_body",
            body_params={"link": link},
            related_type="booking",
            related_id=booking.id,
        )
        await db.commit()
        await db.refresh(notification)
        await notifications_service.publish_realtime(notification, locale=booking.locale)
        logger.info("Sent cancelled-no-payment email for %s to %s", booking.reference, customer.email)
