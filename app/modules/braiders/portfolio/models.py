import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.braiders.models import BioSource


class PortfolioImage(Base):
    __tablename__ = "portfolio_images"
    __table_args__ = (
        UniqueConstraint("braider_id", "position", name="uq_portfolio_image_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    braider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("braider_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    caption_en: Mapped[str | None] = mapped_column(String(300), nullable=True)
    caption_de: Mapped[str | None] = mapped_column(String(300), nullable=True)
    caption_fr: Mapped[str | None] = mapped_column(String(300), nullable=True)
    caption_en_source: Mapped[BioSource | None] = mapped_column(
        Enum(BioSource, name="bio_source"), nullable=True
    )
    caption_de_source: Mapped[BioSource | None] = mapped_column(
        Enum(BioSource, name="bio_source"), nullable=True
    )
    caption_fr_source: Mapped[BioSource | None] = mapped_column(
        Enum(BioSource, name="bio_source"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
