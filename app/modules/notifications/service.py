import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ws
from app.core.config import get_settings
from app.core.exceptions import InvalidDateRangeError, NotificationNotFoundError
from app.core.i18n import t
from app.core.pagination import PaginatedData, PaginationParams
from app.modules.notifications import repository as notifications_repo
from app.modules.notifications.models import Notification, NotificationType
from app.modules.notifications.schemas import DeleteNotificationResponse, NotificationResponse

settings = get_settings()


def _to_response(notification: Notification, *, locale: str) -> NotificationResponse:
    params = notification.body_params or {}
    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        title=t(notification.title_key, locale, **params),
        body=t(notification.body_key, locale, **params),
        related_type=notification.related_type,
        related_id=notification.related_id,
        is_read=notification.is_read,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


async def create(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: NotificationType,
    title_key: str,
    body_key: str,
    body_params: dict | None = None,
    related_type: str | None = None,
    related_id: uuid.UUID | None = None,
) -> Notification:
    """Adds+flushes a Notification onto the caller's own transaction - it's
    the caller's job to commit (typically alongside whatever triggered it,
    e.g. a chat message) and then call `publish_realtime` afterward."""
    return await notifications_repo.create_notification(
        db,
        user_id=user_id,
        type=type,
        title_key=title_key,
        body_key=body_key,
        body_params=body_params or {},
        related_type=related_type,
        related_id=related_id,
    )


async def publish_realtime(notification: Notification, *, locale: str) -> None:
    """Only call after the notification's transaction has committed - the
    client may fetch it over REST the instant this event lands."""
    await ws.publish_event(
        notification.user_id,
        {"type": "notification", "notification": _to_response(notification, locale=locale).model_dump(mode="json")},
    )


async def list_notifications(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    params: PaginationParams,
    is_read: bool | None,
    date_from: datetime | None,
    date_to: datetime | None,
    locale: str,
) -> PaginatedData[NotificationResponse]:
    if date_from is not None and date_to is not None and date_to < date_from:
        raise InvalidDateRangeError()

    items, meta = await notifications_repo.list_for_user(
        db, user_id, params=params, is_read=is_read, date_from=date_from, date_to=date_to
    )
    return PaginatedData(items=[_to_response(n, locale=locale) for n in items], pagination=meta)


async def mark_read(
    db: AsyncSession, *, user_id: uuid.UUID, notification_id: uuid.UUID, locale: str
) -> NotificationResponse:
    notification = await notifications_repo.get_by_id(db, notification_id)
    if notification is None or notification.user_id != user_id:
        raise NotificationNotFoundError()

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(notification)

    return _to_response(notification, locale=locale)


async def mark_all_read(db: AsyncSession, *, user_id: uuid.UUID) -> int:
    count = await notifications_repo.mark_all_read(db, user_id, at=datetime.now(UTC))
    await db.commit()
    return count


async def delete_notification(
    db: AsyncSession, *, user_id: uuid.UUID, notification_id: uuid.UUID, locale: str
) -> DeleteNotificationResponse:
    notification = await notifications_repo.get_by_id(db, notification_id)
    if notification is None or notification.user_id != user_id:
        raise NotificationNotFoundError()

    await db.delete(notification)
    await db.commit()
    return DeleteNotificationResponse(message=t("notifications.deleted", locale))
