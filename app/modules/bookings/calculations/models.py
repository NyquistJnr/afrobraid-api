import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.currency import Currency
from app.core.database import Base
from app.modules.platform_settings.models import SettingValueType


class BookingCalculationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"


class BookingCalculation(Base):
    """A disposable, unauthenticated price quote - has no owner and can
    never be used for authorization, only as an input echo. `POST /bookings`
    (from Phase 2 onward) re-derives and re-authorizes everything itself
    rather than trusting this row; consuming a calculation only saves the
    customer from re-entering their selection.

    Every rate (`platform_fee_*`, `vat_service_*`, `vat_platform_fee_*`,
    `deposit_*`) is snapshotted from `PlatformSettings` at calculation time
    so a rate change mid-quote can't silently retarget an in-flight total.
    `deposit_amount`/`balance_amount` are indicative only - no `starts_at`
    is known yet, so the real full-upfront-vs-deposit decision is made
    again, for real, when the booking is created.
    """

    __tablename__ = "booking_calculations"
    __table_args__ = (
        CheckConstraint(
            "service_subtotal >= 0 AND travel_fee >= 0 AND subtotal >= 0 AND "
            "platform_fee_value >= 0 AND platform_fee >= 0 AND "
            "vat_service_value >= 0 AND vat_platform_fee_value >= 0 AND "
            "vat_on_service >= 0 AND vat_on_platform_fee >= 0 AND vat_total >= 0 AND "
            "total >= 0 AND deposit_value >= 0 AND deposit_amount >= 0 AND balance_amount >= 0 AND "
            "subtotal = service_subtotal + travel_fee AND "
            "total = subtotal + platform_fee + vat_total AND "
            "vat_total = vat_on_service + vat_on_platform_fee AND "
            "deposit_amount + balance_amount = total",
            name="ck_booking_calculations_amounts",
        ),
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
    braider_style_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("braider_styles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    style_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("styles.id"), nullable=False
    )
    style_variation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("style_variations.id"), nullable=True
    )
    # The braider-scoped join-row id the client actually sent (see
    # BookingCalculationInput) - echoed back with no FK (same "input echo,
    # not authorization" reasoning as booking_calculation_addons) purely so
    # a PATCH that omits this field can carry the existing selection
    # forward without a braider_style_variations reverse lookup.
    braider_style_variation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    is_mobile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    client_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    client_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    client_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    currency: Mapped[Currency] = mapped_column(
        Enum(Currency, name="currency"), nullable=False, default=Currency.EUR
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    service_subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    travel_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    platform_fee_type: Mapped[SettingValueType] = mapped_column(
        Enum(SettingValueType, name="setting_value_type"), nullable=False
    )
    platform_fee_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    vat_service_type: Mapped[SettingValueType] = mapped_column(
        Enum(SettingValueType, name="setting_value_type"), nullable=False
    )
    vat_service_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_on_service: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    vat_platform_fee_type: Mapped[SettingValueType] = mapped_column(
        Enum(SettingValueType, name="setting_value_type"), nullable=False
    )
    vat_platform_fee_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_on_platform_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    vat_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    deposit_type: Mapped[SettingValueType] = mapped_column(
        Enum(SettingValueType, name="setting_value_type"), nullable=False
    )
    deposit_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    deposit_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    balance_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    status: Mapped[BookingCalculationStatus] = mapped_column(
        Enum(BookingCalculationStatus, name="booking_calculation_status"),
        nullable=False,
        default=BookingCalculationStatus.DRAFT,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # No FK yet - the `bookings` table doesn't exist until Phase 2, which
    # adds the FK via ALTER TABLE once it does.
    consumed_by_booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Salted SHA-256 of the caller's IP, never the raw address - an IP is
    # personal data under GDPR and there's no lawful basis for storing it
    # against this anonymous, unauthenticated actor.
    client_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BookingCalculationAddon(Base):
    """One selected add-on line on a calculation. `braider_style_addon_id`/
    `addon_id` deliberately carry no FK, mirroring the historical-snapshot
    convention used for booking receipt lines from Phase 2 onward - even
    though this row is short-lived (see `expires_at`), a braider deleting
    the add-on mid-quote must never cascade-delete or orphan this row."""

    __tablename__ = "booking_calculation_addons"
    __table_args__ = (
        UniqueConstraint(
            "booking_calculation_id", "braider_style_addon_id", name="uq_booking_calculation_addon"
        ),
        CheckConstraint("price >= 0", name="ck_booking_calculation_addons_price"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    booking_calculation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking_calculations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    braider_style_addon_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    addon_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
