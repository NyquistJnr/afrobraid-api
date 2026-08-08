import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.notifications.models import NotificationType


class NotificationResponse(BaseModel):
    id: uuid.UUID
    type: NotificationType
    title: str
    body: str
    related_type: str | None
    related_id: uuid.UUID | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class MarkAllReadResponse(BaseModel):
    marked_count: int


class DeleteNotificationResponse(BaseModel):
    message: str
