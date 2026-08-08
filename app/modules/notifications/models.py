import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NotificationType(str, enum.Enum):
    CHAT_NEW_MESSAGE = "CHAT_NEW_MESSAGE"
    CHAT_MESSAGE_FLAGGED = "CHAT_MESSAGE_FLAGGED"


class Notification(Base):
    """Generic, multi-language notification for any user. Text isn't stored
    or machine-translated per row - `title_key`/`body_key` are app.core.i18n
    keys rendered on read in whatever locale the request/socket is currently
    in (`body_params` fills in the template), the same key+params pattern
    AppError already uses for error messages. `related_type`/`related_id`
    let the client deep-link (e.g. "chat_thread"/<thread_id>) without this
    table needing an FK to every possible source table.
    """

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType, name="notification_type"), nullable=False)
    title_key: Mapped[str] = mapped_column(String(100), nullable=False)
    body_key: Mapped[str] = mapped_column(String(100), nullable=False)
    body_params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    related_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
