import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.bookings.enums import (
    BalanceChargeState,
    BookingItemType,
    BookingStatus,
    PaymentPurpose,
    PaymentSchedule,
    PaymentStatus,
)
from app.modules.platform_settings.models import SettingValueType


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            "subtotal + platform_fee + vat_total = total", name="ck_bookings_pricing_total"
        ),
        CheckConstraint(
            "vat_on_service + vat_on_platform_fee = vat_total", name="ck_bookings_pricing_vat_total"
        ),
        CheckConstraint(
            "braider_share_deposit + braider_share_balance = braider_share_total",
            name="ck_bookings_pricing_braider_shares",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    braider_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    status: Mapped[BookingStatus] = mapped_column(
        postgresql.ENUM(BookingStatus, create_type=False), nullable=False
    )

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    blocked_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    blocked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    braider_timezone: Mapped[str] = mapped_column(String(50), nullable=False)

    client_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    client_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    client_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)

    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_on_service: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_on_platform_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    deposit_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    braider_share_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    braider_share_deposit: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    braider_share_balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    platform_fee_type: Mapped[SettingValueType] = mapped_column(
        postgresql.ENUM(SettingValueType, create_type=False, name="settingvaluetype"),
        nullable=False,
    )
    platform_fee_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_service_type: Mapped[SettingValueType] = mapped_column(
        postgresql.ENUM(SettingValueType, create_type=False, name="settingvaluetype"),
        nullable=False,
    )
    vat_service_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_platform_fee_type: Mapped[SettingValueType] = mapped_column(
        postgresql.ENUM(SettingValueType, create_type=False, name="settingvaluetype"),
        nullable=False,
    )
    vat_platform_fee_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    deposit_type: Mapped[SettingValueType] = mapped_column(
        postgresql.ENUM(SettingValueType, create_type=False, name="settingvaluetype"),
        nullable=False,
    )
    deposit_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    braider_vat_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    braider_vat_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    payment_schedule: Mapped[PaymentSchedule] = mapped_column(
        postgresql.ENUM(PaymentSchedule, create_type=False), nullable=False
    )
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    balance_charge_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    balance_charge_state: Mapped[BalanceChargeState | None] = mapped_column(
        postgresql.ENUM(BalanceChargeState, create_type=False), nullable=True
    )
    balance_charge_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    balance_charge_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    appointment_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    balance_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)

    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_payment_method_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_card_exp_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stripe_card_exp_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    terms_version: Mapped[str] = mapped_column(String(20), nullable=False)
    terms_accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)

    items: Mapped[list["BookingItem"]] = relationship("BookingItem", back_populates="booking", cascade="all, delete-orphan")
    payments: Mapped[list["BookingPayment"]] = relationship("BookingPayment", back_populates="booking", cascade="all, delete-orphan")


class BookingItem(Base):
    __tablename__ = "booking_items"

    id: Mapped[uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    item_type: Mapped[BookingItemType] = mapped_column(postgresql.ENUM(BookingItemType, create_type=False), nullable=False)

    source_style_id: Mapped[uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    source_style_variation_id: Mapped[uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    source_addon_id: Mapped[uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    source_braider_style_addon_id: Mapped[uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)

    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_de: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_fr: Mapped[str | None] = mapped_column(String(255), nullable=True)

    line_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    booking: Mapped["Booking"] = relationship("Booking", back_populates="items")


class BookingPayment(Base):
    __tablename__ = "booking_payments"
    __table_args__ = (
        Index("uq_booking_payment_succeeded", "booking_id", "purpose", unique=True, postgresql_where="(status = 'SUCCEEDED')"),
    )

    id: Mapped[uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    purpose: Mapped[PaymentPurpose] = mapped_column(postgresql.ENUM(PaymentPurpose, create_type=False), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(postgresql.ENUM(PaymentStatus, create_type=False), nullable=False)

    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    braider_share_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_refunded_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    amount_transferred_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_charge_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_off_session: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    transfer_group: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    booking: Mapped["Booking"] = relationship("Booking", back_populates="payments")


class StripeWebhookEvent(Base):
    __tablename__ = "stripe_webhook_events"

    stripe_event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
