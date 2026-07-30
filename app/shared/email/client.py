import asyncio
import logging

import resend

from app.core.config import get_settings

settings = get_settings()
resend.api_key = settings.resend_api_key

logger = logging.getLogger("app.email")


async def send_email(*, to: str, subject: str, html: str) -> None:
    if settings.environment == "test":
        logger.info("Test environment: skipping real send (to=%s, subject=%s)", to, subject)
        return

    def _send() -> None:
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": [to],
                "subject": subject,
                "html": html,
            }
        )

    await asyncio.to_thread(_send)
