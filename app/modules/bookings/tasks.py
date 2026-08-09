import logging
import uuid

from app.core.database import AsyncSessionLocal
from app.core.money import from_minor_units
from app.modules.bookings import repository as bookings_repo
from app.modules.braiders import repository as braiders_repo
from app.modules.styles import repository as styles_repo
from app.modules.users import repository as users_repo
from app.shared.email.client import send_email
from app.shared.email.templates.booking_email import render_booking_confirmed_email
from app.shared.email.templates.receipt_email import render_payment_receipt_email

logger = logging.getLogger("app.tasks.bookings")

TASK_SEND_BOOKING_CONFIRMED_EMAIL = "send_booking_confirmed_email_task"
TASK_SEND_PAYMENT_RECEIPT_EMAIL = "send_payment_receipt_email_task"


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
