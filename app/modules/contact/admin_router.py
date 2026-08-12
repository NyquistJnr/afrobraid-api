import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginationParams
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.contact import service
from app.modules.contact.enums import ContactPlatform, ContactPurpose
from app.modules.contact.schemas import (
    AdminContactSubmissionResponse,
    PaginatedAdminContactSubmissionsResponse,
)
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/admin/contact-submissions", tags=["Admin - Contact"])

_require_admin = require_roles(UserType.ADMIN)


@router.get(
    "",
    response_model=APIResponse[PaginatedAdminContactSubmissionsResponse],
    summary="List Contact Us submissions",
    description=(
        "Admin inbox for public Contact Us submissions. Filter by app platform, "
        "purpose, read status, created date range, and free-text search across "
        "name, email, phone, subject, and message."
    ),
)
async def list_contact_submissions(
    platform: ContactPlatform | None = Query(default=None),
    purpose: ContactPurpose | None = Query(default=None),
    is_read: bool | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    params: PaginationParams = Depends(),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedAdminContactSubmissionsResponse]:
    result = await service.list_admin_contact_submissions(
        db,
        params=params,
        platform=platform,
        purpose=purpose,
        is_read=is_read,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    return APIResponse(data=result)


@router.get(
    "/{submission_id}",
    response_model=APIResponse[AdminContactSubmissionResponse],
    summary="Get a Contact Us submission",
)
async def get_contact_submission(
    submission_id: uuid.UUID,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminContactSubmissionResponse]:
    result = await service.get_admin_contact_submission(db, submission_id)
    return APIResponse(data=result)


@router.post(
    "/{submission_id}/mark-read",
    response_model=APIResponse[AdminContactSubmissionResponse],
    summary="Mark a Contact Us submission as read",
)
async def mark_contact_submission_read(
    submission_id: uuid.UUID,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminContactSubmissionResponse]:
    result = await service.mark_admin_contact_submission_read(
        db, submission_id, admin_user_id=user.id
    )
    return APIResponse(data=result)


@router.post(
    "/{submission_id}/mark-unread",
    response_model=APIResponse[AdminContactSubmissionResponse],
    summary="Mark a Contact Us submission as unread",
)
async def mark_contact_submission_unread(
    submission_id: uuid.UUID,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminContactSubmissionResponse]:
    result = await service.mark_admin_contact_submission_unread(db, submission_id)
    return APIResponse(data=result)
