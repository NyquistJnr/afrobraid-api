import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginationMeta, PaginationParams, paginate
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


async def get_submission_by_id(
    db: AsyncSession, submission_id: uuid.UUID
) -> ContactSubmission | None:
    return await db.get(ContactSubmission, submission_id)


def _apply_date_filters(stmt, *, date_from: date | None, date_to: date | None):
    if date_from is not None:
        stmt = stmt.where(
            ContactSubmission.created_at >= datetime.combine(date_from, time.min, tzinfo=UTC)
        )
    if date_to is not None:
        stmt = stmt.where(
            ContactSubmission.created_at
            < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC)
        )
    return stmt


async def list_submissions_for_admin(
    db: AsyncSession,
    *,
    params: PaginationParams,
    platform: ContactPlatform | None = None,
    purpose: ContactPurpose | None = None,
    is_read: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
) -> tuple[list[ContactSubmission], PaginationMeta]:
    stmt = select(ContactSubmission)
    if platform is not None:
        stmt = stmt.where(ContactSubmission.platform == platform)
    if purpose is not None:
        stmt = stmt.where(ContactSubmission.purpose == purpose)
    if is_read is not None:
        stmt = stmt.where(ContactSubmission.is_read == is_read)
    stmt = _apply_date_filters(stmt, date_from=date_from, date_to=date_to)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                ContactSubmission.first_name.ilike(pattern),
                ContactSubmission.last_name.ilike(pattern),
                ContactSubmission.email.ilike(pattern),
                ContactSubmission.phone_number.ilike(pattern),
                ContactSubmission.subject.ilike(pattern),
                ContactSubmission.message.ilike(pattern),
            )
        )
    stmt = stmt.order_by(ContactSubmission.created_at.desc(), ContactSubmission.id.desc())
    return await paginate(db, stmt, params)


async def mark_submission_read(
    db: AsyncSession, submission: ContactSubmission, *, admin_user_id: uuid.UUID
) -> ContactSubmission:
    submission.is_read = True
    submission.read_at = datetime.now(UTC)
    submission.read_by_admin_id = admin_user_id
    await db.flush()
    return submission


async def mark_submission_unread(
    db: AsyncSession, submission: ContactSubmission
) -> ContactSubmission:
    submission.is_read = False
    submission.read_at = None
    submission.read_by_admin_id = None
    await db.flush()
    return submission
