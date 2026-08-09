from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contact.enums import ContactPlatform, ContactPurpose
from app.modules.contact.models import ContactSubmission


async def create_submission(
    db: AsyncSession,
    *,
    first_name: str,
    last_name: str,
    phone_number: str,
    email: str,
    subject: str | None,
    message: str,
    platform: ContactPlatform,
    purpose: ContactPurpose,
) -> ContactSubmission:
    submission = ContactSubmission(
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        email=email,
        subject=subject,
        message=message,
        platform=platform,
        purpose=purpose,
    )
    db.add(submission)
    await db.flush()
    return submission
