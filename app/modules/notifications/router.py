import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginatedData, PaginationParams
from app.core.response import APIResponse
from app.modules.auth.dependencies import get_current_user
from app.modules.notifications import service
from app.modules.notifications.schemas import (
    DeleteNotificationResponse,
    MarkAllReadResponse,
    NotificationResponse,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.get(
    "",
    response_model=APIResponse[PaginatedData[NotificationResponse]],
    summary="List your notifications",
    description="Paginated, newest first. Filter with `is_read` and/or `date_from`/`date_to` "
    "(both ISO 8601, compared against when the notification was created). `title`/`body` are "
    "rendered in your current locale (`?lang=` or Accept-Language).",
)
async def list_notifications(
    request: Request,
    is_read: bool | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    params: PaginationParams = Depends(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedData[NotificationResponse]]:
    result = await service.list_notifications(
        db,
        user_id=user.id,
        params=params,
        is_read=is_read,
        date_from=date_from,
        date_to=date_to,
        locale=_locale(request),
    )
    return APIResponse(data=result)


@router.patch(
    "/{notification_id}/read",
    response_model=APIResponse[NotificationResponse],
    summary="Mark a notification as read",
)
async def mark_read(
    notification_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[NotificationResponse]:
    result = await service.mark_read(
        db, user_id=user.id, notification_id=notification_id, locale=_locale(request)
    )
    return APIResponse(data=result)


@router.post(
    "/read-all",
    response_model=APIResponse[MarkAllReadResponse],
    summary="Mark all of your notifications as read",
)
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[MarkAllReadResponse]:
    count = await service.mark_all_read(db, user_id=user.id)
    return APIResponse(data=MarkAllReadResponse(marked_count=count))


@router.delete(
    "/{notification_id}",
    response_model=APIResponse[DeleteNotificationResponse],
    summary="Delete a notification",
)
async def delete_notification(
    notification_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[DeleteNotificationResponse]:
    result = await service.delete_notification(
        db, user_id=user.id, notification_id=notification_id, locale=_locale(request)
    )
    return APIResponse(data=result)
