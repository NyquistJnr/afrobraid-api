import logging
import uuid
from datetime import datetime

from app.core.database import AsyncSessionLocal
from app.core.money import from_minor_units
from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.enums import PaymentPurpose
from app.modules.braiders import repository as braiders_repo
from app.modules.notifications import service as notifications_service
from app.modules.notifications.models import NotificationType
from app.modules.styles import repository as styles_repo
from app.modules.users import repository as users_repo
from app.shared.email.client import send_email
from app.shared.email.templates.booking_email import (
    render_booking_confirmed_email,
    render_booking_rescheduled_email,
)
from app.shared.email.templates.receipt_email import render_payment_receipt_email
from app.shared.links import build_frontend_url

logger = logging.getLogger("app.tasks.bookings")

TASK_SEND_BOOKING_CONFIRMED_EMAIL = "send_booking_confirmed_email_task"
TASK_SEND_PAYMENT_RECEIPT_EMAIL = "send_payment_receipt_email_task"
TASK_SEND_PAYMENT_NOTIFICATION = "send_payment_notification_task"
TASK_SEND_BOOKING_RESCHEDULED_EMAIL = "send_booking_rescheduled_email_task"
TASK_SEND_BOOKING_RESCHEDULED_NOTIFICATION = "send_booking_rescheduled_notification_task"

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
            "link": build_frontend_url(locale=booking.locale, path=f"bookings/{booking.id}"),
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
        link = build_frontend_url(locale=booking.locale, path=f"bookings/{booking.id}")
        body_params = {"link": link}

        customer_notification = await notifications_service.create(
            db,
            user_id=booking.customer_id,
            type=NotificationType.BOOKING_RESCHEDULED,
            title_key="notifications.booking_rescheduled_customer_title",
            body_key="notifications.booking_rescheduled_customer_body",
            body_params=body_params,
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
                body_params=body_params,
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
