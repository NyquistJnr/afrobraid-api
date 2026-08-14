import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
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

from app.core.currency import Currency
from app.core.database import Base
from app.modules.bookings.enums import BraiderVatStatus, ReceiptType


class ReceiptCounter(Base):
    """One row per calendar year, locked FOR UPDATE inside the receipt
    insert to hand out gapless numbers (design correction #4) -
    `nextval()` isn't usable here because a rolled-back transaction burns
    a sequence value permanently, which a legal receipt number can't do.
    Never reset mid-year; `last_number` only ever increases."""

    __tablename__ = "receipt_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Receipt(Base):
    """An immutable legal document snapshot - `html` is rendered once at
    issuance and never re-rendered, so a receipt a customer already
    downloaded never silently changes even if the booking's locale or the
    template itself changes later. `credit_note_for_receipt_id` is what
    lets a CREDIT_NOTE reference the INVOICE it corrects (a §14c UStG
    requirement); `booking_refund_id` ties it to the refund that caused
    it. `prior_receipts_total` is what makes a BALANCE receipt a correct
    *Schlussrechnung* - it deducts the *Anzahlungsrechnung* (the DEPOSIT
    receipt's amount) rather than re-showing the full total as newly due.
    """

    __tablename__ = "receipts"
    __table_args__ = (
        CheckConstraint("amount_total >= 0 AND prior_receipts_total >= 0", name="ck_receipts_amounts"),
        UniqueConstraint("receipt_number", name="uq_receipts_receipt_number"),
        UniqueConstraint("public_token", name="uq_receipts_public_token"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    booking_payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("booking_payments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    booking_refund_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("booking_refunds.id", ondelete="CASCADE"), nullable=True
    )
    credit_note_for_receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipts.id"), nullable=True
    )

    type: Mapped[ReceiptType] = mapped_column(
        Enum(ReceiptType, name="receipt_type"), nullable=False, default=ReceiptType.INVOICE
    )
    receipt_number: Mapped[str] = mapped_column(String(20), nullable=False)
    public_token: Mapped[str] = mapped_column(String(64), nullable=False)
    locale: Mapped[str] = mapped_column(String(5), nullable=False)

    amount_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    prior_receipts_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    currency: Mapped[Currency] = mapped_column(Enum(Currency, name="currency"), nullable=False)

    # Snapshotted off the booking at issuance - see Booking.braider_vat_status.
    braider_vat_status: Mapped[BraiderVatStatus] = mapped_column(
        Enum(BraiderVatStatus, name="braider_vat_status"), nullable=False
    )
    braider_vat_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

    html: Mapped[str] = mapped_column(Text, nullable=False)

    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
