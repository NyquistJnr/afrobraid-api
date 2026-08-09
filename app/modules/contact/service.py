from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import t
from app.modules.contact import repository as contact_repo
from app.modules.contact.schemas import ContactSubmissionRequest, ContactSubmissionResponse


async def submit_contact_form(
    db: AsyncSession, *, data: ContactSubmissionRequest, locale: str
) -> ContactSubmissionResponse:
    submission = await contact_repo.create_submission(
        db,
        first_name=data.first_name,
        last_name=data.last_name,
        phone_number=data.phone_number,
        email=data.email,
        subject=data.subject,
        message=data.message,
        platform=data.platform,
        purpose=data.purpose,
    )
    await db.commit()

    return ContactSubmissionResponse(id=submission.id, message=t("contact.submitted", locale))
