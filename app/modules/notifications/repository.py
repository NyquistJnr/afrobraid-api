import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginationParams, paginate
from app.modules.notifications.models import Notification, NotificationType


async def create_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: NotificationType,
    title_key: str,
    body_key: str,
    body_params: dict,
    related_type: str | None,
    related_id: uuid.UUID | None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        type=type,
        title_key=title_key,
        body_key=body_key,
        body_params=body_params,
        related_type=related_type,
        related_id=related_id,
    )
    db.add(notification)
    await db.flush()
    return notification


async def get_by_id(db: AsyncSession, notification_id: uuid.UUID) -> Notification | None:
    return await db.get(Notification, notification_id)


async def list_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    params: PaginationParams,
    is_read: bool | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> tuple[list[Notification], object]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if is_read is not None:
        stmt = stmt.where(Notification.is_read == is_read)
    if date_from is not None:
        stmt = stmt.where(Notification.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Notification.created_at <= date_to)
    stmt = stmt.order_by(Notification.created_at.desc())
    return await paginate(db, stmt, params)


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID, *, at: datetime) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=at)
    )
    return result.rowcount or 0
