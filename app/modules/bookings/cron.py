import logging

from app.core.database import AsyncSessionLocal
from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.tasks import TASK_CHARGE_BOOKING_BALANCE

logger = logging.getLogger("app.cron.bookings")

_EXPIRE_BATCH_LIMIT = 5000
_BALANCE_SWEEP_BATCH_LIMIT = 500


async def expire_booking_holds_cron(ctx: dict) -> None:
    """Releases a PENDING_PAYMENT booking's calendar hold once its
    hold_expires_at has passed with no successful payment - runs every
    minute, matching the plan's `expire_booking_holds` cron."""
    async with AsyncSessionLocal() as db:
        expired = await bookings_repo.expire_stale_holds(db, limit=_EXPIRE_BATCH_LIMIT)
        await db.commit()
        if expired:
            logger.info("Expired %d stale PENDING_PAYMENT booking holds", expired)


async def sweep_balance_charges_cron(ctx: dict) -> None:
    """The primary balance driver (plan: `sweep_balance_charges`, every 5m).
    Claims every booking whose deposit-then-balance schedule has come due
    (SCHEDULED -> DUE, batched and atomic - see claim_due_balance_charges)
    and enqueues one charge_booking_balance_task per booking. Deliberately
    does no Stripe I/O itself - that happens in the task, off the cron's
    critical path, so a slow/stuck charge can't back up the whole sweep."""
    async with AsyncSessionLocal() as db:
        claimed = await bookings_repo.claim_due_balance_charges(db, limit=_BALANCE_SWEEP_BATCH_LIMIT)
        await db.commit()
    for booking_id in claimed:
        await ctx["redis"].enqueue_job(TASK_CHARGE_BOOKING_BALANCE, booking_id=str(booking_id))
    if claimed:
        logger.info("Enqueued %d due balance charges", len(claimed))
