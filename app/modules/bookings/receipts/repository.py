import secrets
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import Currency
from app.modules.bookings.enums import BraiderVatStatus, ReceiptType
from app.modules.bookings.receipts.models import Receipt, ReceiptCounter


async def _next_receipt_number(db: AsyncSession, *, year: int) -> str:
    """Locks (and, if needed, creates) this year's counter row, increments
    it, and returns the formatted number - all inside the caller's
    transaction, so the increment only survives if that transaction
    commits (see the model docstring on why nextval() can't be used here).
    INSERT ... ON CONFLICT DO NOTHING handles the year-rollover race
    (two concurrent first-receipts-of-the-year) without needing a
    savepoint; the following SELECT ... FOR UPDATE is what actually
    serializes the increment itself."""
    await db.execute(
        pg_insert(ReceiptCounter)
        .values(year=year, last_number=0)
        .on_conflict_do_nothing(index_elements=["year"])
    )
    result = await db.execute(
        select(ReceiptCounter).where(ReceiptCounter.year == year).with_for_update()
    )
    counter = result.scalar_one()
    counter.last_number += 1
    await db.flush()
    return f"{year}-{counter.last_number:06d}"


async def create_receipt(
    db: AsyncSession,
    *,
    booking_id: uuid.UUID,
    booking_payment_id: uuid.UUID,
    booking_refund_id: uuid.UUID | None,
    credit_note_for_receipt_id: uuid.UUID | None,
    type: ReceiptType,
    locale: str,
    amount_total: Decimal,
    prior_receipts_total: Decimal,
    currency: Currency,
    braider_vat_status: BraiderVatStatus,
    braider_vat_number: str | None,
    html: str,
) -> Receipt:
    receipt_number = await _next_receipt_number(db, year=datetime.now(UTC).year)
    receipt = Receipt(
        booking_id=booking_id,
        booking_payment_id=booking_payment_id,
        booking_refund_id=booking_refund_id,
        credit_note_for_receipt_id=credit_note_for_receipt_id,
        type=type,
        receipt_number=receipt_number,
        public_token=secrets.token_urlsafe(24),
        locale=locale,
        amount_total=amount_total,
        prior_receipts_total=prior_receipts_total,
        currency=currency,
        braider_vat_status=braider_vat_status,
        braider_vat_number=braider_vat_number,
        html=html,
    )
    db.add(receipt)
    await db.flush()
    return receipt


async def get_receipt_by_public_token(db: AsyncSession, public_token: str) -> Receipt | None:
    result = await db.execute(select(Receipt).where(Receipt.public_token == public_token))
    return result.scalar_one_or_none()


async def get_invoice_receipt_for_payment(db: AsyncSession, booking_payment_id: uuid.UUID) -> Receipt | None:
    result = await db.execute(
        select(Receipt).where(
            Receipt.booking_payment_id == booking_payment_id, Receipt.type == ReceiptType.INVOICE
        )
    )
    return result.scalar_one_or_none()


async def list_invoice_receipts_for_booking(db: AsyncSession, booking_id: uuid.UUID) -> list[Receipt]:
    result = await db.execute(
        select(Receipt)
        .where(Receipt.booking_id == booking_id, Receipt.type == ReceiptType.INVOICE)
        .order_by(Receipt.issued_at)
    )
    return list(result.scalars().all())


async def list_receipts_for_booking(db: AsyncSession, booking_id: uuid.UUID) -> list[Receipt]:
    result = await db.execute(
        select(Receipt).where(Receipt.booking_id == booking_id).order_by(Receipt.issued_at)
    )
    return list(result.scalars().all())
