from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import from_minor_units
from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.enums import ReceiptType
from app.modules.bookings.models import Booking, BookingPayment, BookingRefund
from app.modules.bookings.receipts import repository as receipts_repo
from app.modules.bookings.receipts.models import Receipt
from app.modules.bookings.receipts.templates import render_receipt_html
from app.modules.braiders import repository as braiders_repo
from app.modules.users import repository as users_repo


async def issue_invoice_receipt(db: AsyncSession, *, booking: Booking, payment: BookingPayment) -> Receipt:
    """Issued the moment a payment succeeds (FULL, DEPOSIT, or BALANCE) -
    called from the same transaction as marking the payment SUCCEEDED, so
    the receipt number is only consumed if that transaction actually
    commits. A DEPOSIT receipt is the *Anzahlungsrechnung*; the following
    BALANCE receipt is the *Schlussrechnung* and deducts it via
    prior_receipts_total."""
    customer = await users_repo.get_user_by_id(db, booking.customer_id)
    braider_profile = await braiders_repo.get_profile_by_id(db, booking.braider_id)
    items = await bookings_repo.list_items(db, booking.id)

    prior_invoices = await receipts_repo.list_invoice_receipts_for_booking(db, booking.id)
    prior_receipts_total = sum((r.amount_total for r in prior_invoices), Decimal("0.00"))
    prior_receipt_number = prior_invoices[-1].receipt_number if prior_invoices else None

    amount_total = from_minor_units(payment.amount_minor)
    customer_name = f"{customer.first_name} {customer.last_name or ''}".strip() if customer else ""
    customer_email = customer.email if customer else ""
    braider_name = braider_profile.business_name if braider_profile else ""

    # The number/issued_at only exist once the row is created (gapless
    # numbering happens inside create_receipt), so this creates a
    # placeholder-html row first and re-renders/updates it immediately
    # after - both still inside the same caller transaction.
    receipt = await receipts_repo.create_receipt(
        db,
        booking_id=booking.id,
        booking_payment_id=payment.id,
        booking_refund_id=None,
        credit_note_for_receipt_id=None,
        type=ReceiptType.INVOICE,
        locale=booking.locale,
        amount_total=amount_total,
        prior_receipts_total=prior_receipts_total,
        currency=booking.currency,
        braider_vat_status=booking.braider_vat_status,
        braider_vat_number=booking.braider_vat_number,
        html="",
    )

    receipt.html = render_receipt_html(
        receipt_type=ReceiptType.INVOICE,
        receipt_number=receipt.receipt_number,
        issued_at=receipt.issued_at,
        locale=booking.locale,
        reference=booking.reference,
        customer_name=customer_name,
        customer_email=customer_email,
        braider_name=braider_name,
        braider_vat_status=booking.braider_vat_status,
        braider_vat_number=booking.braider_vat_number,
        items=items,
        amount_total=amount_total,
        prior_receipts_total=prior_receipts_total,
        prior_receipt_number=prior_receipt_number,
        currency=booking.currency.value,
        credit_note_for_receipt_number=None,
    )
    await db.flush()
    return receipt


async def issue_credit_note(
    db: AsyncSession, *, booking: Booking, payment: BookingPayment, refund: BookingRefund
) -> Receipt:
    """Issued alongside a braider-initiated cancellation's refund (design
    correction: a refund without a corresponding credit note is a §14c
    UStG problem - VAT shown on the original invoice is still owed unless
    formally corrected)."""
    customer = await users_repo.get_user_by_id(db, booking.customer_id)
    braider_profile = await braiders_repo.get_profile_by_id(db, booking.braider_id)

    original_invoice = await receipts_repo.get_invoice_receipt_for_payment(db, payment.id)
    credit_note_for_receipt_number = original_invoice.receipt_number if original_invoice else None

    amount_total = from_minor_units(refund.amount_minor)
    customer_name = f"{customer.first_name} {customer.last_name or ''}".strip() if customer else ""
    customer_email = customer.email if customer else ""
    braider_name = braider_profile.business_name if braider_profile else ""

    receipt = await receipts_repo.create_receipt(
        db,
        booking_id=booking.id,
        booking_payment_id=payment.id,
        booking_refund_id=refund.id,
        credit_note_for_receipt_id=original_invoice.id if original_invoice else None,
        type=ReceiptType.CREDIT_NOTE,
        locale=booking.locale,
        amount_total=amount_total,
        prior_receipts_total=Decimal("0.00"),
        currency=booking.currency,
        braider_vat_status=booking.braider_vat_status,
        braider_vat_number=booking.braider_vat_number,
        html="",
    )

    items = await bookings_repo.list_items(db, booking.id)
    receipt.html = render_receipt_html(
        receipt_type=ReceiptType.CREDIT_NOTE,
        receipt_number=receipt.receipt_number,
        issued_at=receipt.issued_at,
        locale=booking.locale,
        reference=booking.reference,
        customer_name=customer_name,
        customer_email=customer_email,
        braider_name=braider_name,
        braider_vat_status=booking.braider_vat_status,
        braider_vat_number=booking.braider_vat_number,
        items=items,
        amount_total=amount_total,
        prior_receipts_total=Decimal("0.00"),
        prior_receipt_number=None,
        currency=booking.currency.value,
        credit_note_for_receipt_number=credit_note_for_receipt_number,
    )
    await db.flush()
    return receipt
