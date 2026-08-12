import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidDateRangeError, NotFoundError
from app.core.i18n import t
from app.core.pagination import PaginationParams
from app.modules.contact import repository as contact_repo
from app.modules.contact.enums import ContactPlatform, ContactPurpose
from app.modules.contact.models import ContactSubmission
from app.modules.contact.schemas import (
    AdminContactSubmissionResponse,
    ContactSubmissionRequest,
    ContactSubmissionResponse,
    PaginatedAdminContactSubmissionsResponse,
)


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


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_to < date_from:
        raise InvalidDateRangeError()


def _to_admin_response(submission: ContactSubmission) -> AdminContactSubmissionResponse:
    return AdminContactSubmissionResponse(
        id=submission.id,
        first_name=submission.first_name,
        last_name=submission.last_name,
        full_name=f"{submission.first_name} {submission.last_name}".strip(),
        phone_number=submission.phone_number,
        email=submission.email,
        subject=submission.subject,
        message=submission.message,
        platform=submission.platform,
        purpose=submission.purpose,
        is_read=submission.is_read,
        read_at=submission.read_at,
        read_by_admin_id=submission.read_by_admin_id,
        created_at=submission.created_at,
    )


async def list_admin_contact_submissions(
    db: AsyncSession,
    *,
    params: PaginationParams,
    platform: ContactPlatform | None = None,
    purpose: ContactPurpose | None = None,
    is_read: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
) -> PaginatedAdminContactSubmissionsResponse:
    _validate_date_range(date_from, date_to)
    items, meta = await contact_repo.list_submissions_for_admin(
        db,
        params=params,
        platform=platform,
        purpose=purpose,
        is_read=is_read,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    return PaginatedAdminContactSubmissionsResponse(
        items=[_to_admin_response(item) for item in items],
        pagination=meta,
    )


async def get_admin_contact_submission(
    db: AsyncSession, submission_id: uuid.UUID
) -> AdminContactSubmissionResponse:
    submission = await contact_repo.get_submission_by_id(db, submission_id)
    if submission is None:
        raise NotFoundError()
    return _to_admin_response(submission)


async def mark_admin_contact_submission_read(
    db: AsyncSession, submission_id: uuid.UUID, *, admin_user_id: uuid.UUID
) -> AdminContactSubmissionResponse:
    submission = await contact_repo.get_submission_by_id(db, submission_id)
    if submission is None:
        raise NotFoundError()
    await contact_repo.mark_submission_read(db, submission, admin_user_id=admin_user_id)
    await db.commit()
    return _to_admin_response(submission)


async def mark_admin_contact_submission_unread(
    db: AsyncSession, submission_id: uuid.UUID
) -> AdminContactSubmissionResponse:
    submission = await contact_repo.get_submission_by_id(db, submission_id)
    if submission is None:
        raise NotFoundError()
    await contact_repo.mark_submission_unread(db, submission)
    await db.commit()
    return _to_admin_response(submission)
