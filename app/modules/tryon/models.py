import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TryOnStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TryOnFailureReason(str, enum.Enum):
    GENERATION_FAILED = "GENERATION_FAILED"
    AI_CREDIT_EXHAUSTED = "AI_CREDIT_EXHAUSTED"


class HairstyleTryOn(Base):
    __tablename__ = "hairstyle_tryons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    style_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("styles.id", ondelete="SET NULL"), nullable=True
    )
    style_variation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("style_variations.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    source_object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[TryOnStatus] = mapped_column(
        Enum(TryOnStatus, name="tryon_status"), nullable=False, default=TryOnStatus.PROCESSING
    )
    failure_reason: Mapped[TryOnFailureReason | None] = mapped_column(
        Enum(TryOnFailureReason, name="tryon_failure_reason"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
