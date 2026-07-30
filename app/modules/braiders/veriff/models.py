import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VeriffSessionStatus(str, enum.Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    RESUBMISSION_REQUESTED = "RESUBMISSION_REQUESTED"
    REVIEW = "REVIEW"
    EXPIRED = "EXPIRED"
    ABANDONED = "ABANDONED"


class VeriffSession(Base):
    __tablename__ = "veriff_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    veriff_session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    verification_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[VeriffSessionStatus] = mapped_column(
        Enum(VeriffSessionStatus, name="veriff_session_status"),
        default=VeriffSessionStatus.CREATED,
        nullable=False,
    )
    decision_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reason_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acceptance_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submission_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_webhook_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
