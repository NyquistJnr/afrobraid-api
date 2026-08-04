import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SettingValueType(str, enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"


class PlatformSettings(Base):
    """Singleton table - always exactly one row, holding the platform-wide
    VAT and platform fee configuration. Like BraiderAvailabilitySettings,
    the single row is fetched-or-created lazily in the service layer rather
    than enforced by a DB constraint."""

    __tablename__ = "platform_settings"
    __table_args__ = (
        CheckConstraint(
            "platform_fee_value >= 0 AND vat_value >= 0 AND "
            "(platform_fee_type != 'PERCENTAGE' OR platform_fee_value <= 100) AND "
            "(vat_type != 'PERCENTAGE' OR vat_value <= 100)",
            name="ck_platform_settings_value_ranges",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    platform_fee_type: Mapped[SettingValueType] = mapped_column(
        Enum(SettingValueType, name="setting_value_type"), nullable=False
    )
    platform_fee_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_type: Mapped[SettingValueType] = mapped_column(
        Enum(SettingValueType, name="setting_value_type"), nullable=False
    )
    vat_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
