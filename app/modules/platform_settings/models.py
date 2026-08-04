import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SettingValueType(str, enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"


class PlatformSettings(Base):
    """Singleton table - always exactly one row, holding the platform-wide
    fee, VAT and deposit configuration. Like BraiderAvailabilitySettings,
    the single row is fetched-or-created lazily in the service layer rather
    than enforced by a DB constraint.

    `vat_type`/`vat_value` is the VAT rate charged on the braider's SERVICE
    (the customer-facing subtotal). `vat_platform_fee_type`/`vat_platform_fee_value`
    is the (independent) VAT rate charged on the platform's own intermediation
    fee - the two are genuinely different taxable supplies (see the booking
    pricing engine for how they're combined), so they are never blended into
    one rate even though both are seeded at the same value today.

    `deposit_type`/`deposit_value` is the upfront-reservation deposit taken
    on a booking made far enough in advance - see `app.modules.bookings.pricing`."""

    __tablename__ = "platform_settings"
    __table_args__ = (
        CheckConstraint(
            "platform_fee_value >= 0 AND vat_value >= 0 AND "
            "vat_platform_fee_value >= 0 AND deposit_value >= 0 AND "
            "(platform_fee_type != 'PERCENTAGE' OR platform_fee_value <= 100) AND "
            "(vat_type != 'PERCENTAGE' OR vat_value <= 100) AND "
            "(vat_platform_fee_type != 'PERCENTAGE' OR vat_platform_fee_value <= 100) AND "
            "(deposit_type != 'PERCENTAGE' OR deposit_value <= 100)",
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
    vat_platform_fee_type: Mapped[SettingValueType] = mapped_column(
        Enum(SettingValueType, name="setting_value_type"), nullable=False
    )
    vat_platform_fee_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    deposit_type: Mapped[SettingValueType] = mapped_column(
        Enum(SettingValueType, name="setting_value_type"), nullable=False
    )
    deposit_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CountryVatSettings(Base):
    """Country-specific overrides for VAT rates. If a country exists in this
    table, its VAT rates override the default PlatformSettings VAT rates."""

    __tablename__ = "country_vat_settings"
    __table_args__ = (
        CheckConstraint(
            "vat_value >= 0 AND vat_platform_fee_value >= 0 AND "
            "(vat_type != 'PERCENTAGE' OR vat_value <= 100) AND "
            "(vat_platform_fee_type != 'PERCENTAGE' OR vat_platform_fee_value <= 100)",
            name="ck_country_vat_settings_value_ranges",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    country: Mapped[str] = mapped_column(String(2), unique=True, index=True, nullable=False)
    vat_type: Mapped[SettingValueType] = mapped_column(
        Enum(SettingValueType, name="setting_value_type"), nullable=False
    )
    vat_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_platform_fee_type: Mapped[SettingValueType] = mapped_column(
        Enum(SettingValueType, name="setting_value_type"), nullable=False
    )
    vat_platform_fee_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
