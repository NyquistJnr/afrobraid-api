"""Braider-payout Stripe plumbing shared by the customer-cancellation
deposit-share release (Phase 4), the completion payout task, and the
dispute-reversal path (both Phase 5). Lives in its own module rather than
`service.py` because `tasks.py` needs it too, and `service.py` already
imports from `tasks.py` (task name constants) - putting it in either of
those would create a circular import.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.enums import TransferStatus
from app.modules.bookings.models import Booking
from app.modules.bookings.payments import client as payments_client

logger = logging.getLogger("app.modules.bookings.payouts")


async def release_braider_shares(db: AsyncSession, booking: Booking, *, connect_account) -> None:
    """One Transfer per succeeded payment that hasn't been paid out yet
    (amount_transferred_minor == 0), for that payment's braider_share_minor
    - source_transaction=<that payment's charge> makes the funds available
    immediately. Never raises: a missing Connect account or a Stripe
    failure is recorded and logged, not raised, so the caller's action
    (a cancellation, a payout sweep) always completes - an
    admin/reconciliation follow-up, same spirit as the plan's
    PAYOUT_BLOCKED handling. Safe to call more than once for the same
    booking - already-transferred payments are skipped, and the
    deterministic idempotency_key plus the partial unique index
    (uq_booking_transfers_active_per_payment) make a concurrent duplicate
    attempt a no-op rather than a double payout."""
    succeeded_payments = await bookings_repo.list_succeeded_payments(db, booking.id)
    for payment in succeeded_payments:
        if payment.braider_share_minor <= 0 or payment.amount_transferred_minor > 0:
            continue
        idempotency_key = f"booking:{booking.id}:transfer:{payment.id}"
        if connect_account is None or payment.stripe_charge_id is None:
            logger.warning(
                "Skipping braider-share transfer for booking %s payment %s - no payable "
                "Connect account or missing charge id",
                booking.reference,
                payment.id,
            )
            continue
        try:
            result = await payments_client.create_transfer(
                amount_minor=payment.braider_share_minor,
                currency=payment.currency.value,
                destination_account_id=connect_account.stripe_account_id,
                source_charge_id=payment.stripe_charge_id,
                transfer_group=payment.transfer_group,
                metadata={"booking_id": str(booking.id), "booking_payment_id": str(payment.id)},
                idempotency_key=idempotency_key,
            )
        except payments_client.StripeApiError as exc:
            transfer = await bookings_repo.create_transfer(
                db,
                booking_id=booking.id,
                booking_payment_id=payment.id,
                destination_account_id=connect_account.stripe_account_id,
                amount_minor=payment.braider_share_minor,
                currency=payment.currency,
                transfer_group=payment.transfer_group,
                idempotency_key=idempotency_key,
            )
            transfer.status = TransferStatus.FAILED
            transfer.failure_message = str(exc)[:500]
            logger.warning(
                "Braider-share transfer failed for booking %s payment %s: %s",
                booking.reference,
                payment.id,
                exc,
            )
            continue
        transfer = await bookings_repo.create_transfer(
            db,
            booking_id=booking.id,
            booking_payment_id=payment.id,
            destination_account_id=connect_account.stripe_account_id,
            amount_minor=payment.braider_share_minor,
            currency=payment.currency,
            transfer_group=payment.transfer_group,
            idempotency_key=idempotency_key,
        )
        transfer.status = TransferStatus.SUCCEEDED
        transfer.stripe_transfer_id = result.id
        payment.amount_transferred_minor = payment.braider_share_minor
        await db.flush()


async def reverse_transfers_for_booking(db: AsyncSession, booking: Booking) -> None:
    """Reverses every PENDING/SUCCEEDED transfer on this booking - used by
    a braider cancellation (defensive; that list is normally empty, since
    the only thing that creates a transfer before COMPLETED is a customer
    cancellation, and the two are mutually exclusive terminal states) and
    by charge.dispute.created (the real case - design correction #6).
    Unlike release_braider_shares, failures here are still just logged and
    recorded, never raised - a dispute must always freeze the booking even
    if the reversal itself can't be completed automatically (e.g. the
    connected account's balance can't cover the clawback)."""
    active_transfers = await bookings_repo.list_active_transfers_for_booking(db, booking.id)
    for transfer in active_transfers:
        if transfer.stripe_transfer_id is None:
            continue
        idempotency_key = f"booking:{booking.id}:transfer_reversal:{transfer.id}"
        try:
            result = await payments_client.reverse_transfer(
                transfer_id=transfer.stripe_transfer_id, idempotency_key=idempotency_key
            )
        except payments_client.StripeApiError as exc:
            reversal = await bookings_repo.create_transfer_reversal(
                db,
                booking_id=booking.id,
                booking_transfer_id=transfer.id,
                amount_minor=transfer.amount_minor,
                currency=transfer.currency,
                idempotency_key=idempotency_key,
            )
            reversal.status = TransferStatus.FAILED
            reversal.failure_message = str(exc)[:500]
            logger.warning(
                "Transfer reversal failed for booking %s transfer %s: %s",
                booking.reference,
                transfer.id,
                exc,
            )
            continue
        reversal = await bookings_repo.create_transfer_reversal(
            db,
            booking_id=booking.id,
            booking_transfer_id=transfer.id,
            amount_minor=transfer.amount_minor,
            currency=transfer.currency,
            idempotency_key=idempotency_key,
        )
        reversal.status = TransferStatus.SUCCEEDED
        reversal.stripe_reversal_id = result.id
        transfer.status = TransferStatus.REVERSED
        await db.flush()
