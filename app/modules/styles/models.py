import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TranslationSource(str, enum.Enum):
    HUMAN = "HUMAN"
    MACHINE = "MACHINE"
    PENDING = "PENDING"
    FAILED = "FAILED"


class StyleCategory(Base):
    __tablename__ = "style_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String(150), nullable=False)
    name_de: Mapped[str | None] = mapped_column(String(150), nullable=True)
    name_fr: Mapped[str | None] = mapped_column(String(150), nullable=True)
    name_en_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    name_de_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    name_fr_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Style(Base):
    __tablename__ = "styles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("style_categories.id"), nullable=True, index=True
    )
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String(150), nullable=False)
    name_de: Mapped[str | None] = mapped_column(String(150), nullable=True)
    name_fr: Mapped[str | None] = mapped_column(String(150), nullable=True)
    name_en_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    name_de_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    name_fr_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_de: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    description_de_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    description_fr_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StyleImage(Base):
    __tablename__ = "style_images"
    __table_args__ = (UniqueConstraint("style_id", "position", name="uq_style_image_position"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    style_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("styles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StyleVariation(Base):
    __tablename__ = "style_variations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    style_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("styles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name_en: Mapped[str] = mapped_column(String(150), nullable=False)
    name_de: Mapped[str | None] = mapped_column(String(150), nullable=True)
    name_fr: Mapped[str | None] = mapped_column(String(150), nullable=True)
    name_en_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    name_de_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    name_fr_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AddOn(Base):
    __tablename__ = "addons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String(150), nullable=False)
    name_de: Mapped[str | None] = mapped_column(String(150), nullable=True)
    name_fr: Mapped[str | None] = mapped_column(String(150), nullable=True)
    name_en_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    name_de_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    name_fr_source: Mapped[TranslationSource | None] = mapped_column(
        Enum(TranslationSource, name="translation_source"), nullable=True
    )
    suggested_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
