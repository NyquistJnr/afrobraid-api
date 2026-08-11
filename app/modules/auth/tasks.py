import logging

from app.core.config import get_settings
from app.modules.auth.models import OtpPurpose
from app.shared.email.client import send_email
from app.shared.email.templates.admin_invite_email import render_admin_invite_email
from app.shared.email.templates.otp_email import (
    render_password_reset_email,
    render_verification_email,
)

logger = logging.getLogger("app.tasks.auth")

settings = get_settings()

TASK_SEND_OTP_EMAIL = "send_otp_email_task"
TASK_SEND_ADMIN_INVITE_EMAIL = "send_admin_invite_email_task"


async def send_otp_email_task(
    ctx: dict,
    *,
    to: str,
    first_name: str,
    code: str,
    minutes: int,
    locale: str,
    purpose: str,
) -> None:
    if purpose == OtpPurpose.EMAIL_VERIFICATION.value:
        subject, html = render_verification_email(
            first_name=first_name, code=code, minutes=minutes, locale=locale
        )
    else:
        subject, html = render_password_reset_email(
            first_name=first_name, code=code, minutes=minutes, locale=locale
        )

    await send_email(to=to, subject=subject, html=html)
    logger.info("Sent %s email to %s", purpose, to)


async def send_admin_invite_email_task(
    ctx: dict,
    *,
    to: str,
    token: str,
    minutes: int,
    locale: str,
) -> None:
    accept_url = f"{settings.frontend_url}/admin/invite/accept?token={token}"
    subject, html = render_admin_invite_email(accept_url=accept_url, minutes=minutes, locale=locale)
    await send_email(to=to, subject=subject, html=html)
    logger.info("Sent admin invite email to %s", to)
