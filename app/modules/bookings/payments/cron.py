import logging
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.payments import repository as payments_repo
from app.modules.bookings.payments import service as payments_service

logger = logging.getLogger("app.cron.bookings.payments")
settings = get_settings()

_RECONCILE_BATCH_LIMIT = 200
_RETRY_BATCH_LIMIT = 200


async def reconcile_stripe_payments_cron(ctx: dict) -> None:
    """Design correction #7's safety net for a webhook that never arrived
    at all - re-fetches the real Stripe status for every payment that's
    been PENDING too long and replays the same handling a live webhook
    would have. Each payment gets its own try/except so one bad row can't
    stall the batch."""
    threshold = datetime.now(UTC) - timedelta(minutes=settings.reconcile_pending_payment_after_minutes)
    async with AsyncSessionLocal() as db:
        stale = await bookings_repo.list_stale_pending_payments(
            db, older_than=threshold, limit=_RECONCILE_BATCH_LIMIT
        )
        reconciled = 0
        for payment in stale:
            try:
                await payments_service.reconcile_pending_payment(db, ctx["redis"], payment)
                reconciled += 1
            except Exception:
                logger.exception("Reconciliation failed for payment %s", payment.id)
                await db.rollback()
        if stale:
            logger.info("Reconciliation swept %d stale pending payments (%d changed)", len(stale), reconciled)


async def retry_webhook_events_cron(ctx: dict) -> None:
    """Design correction #7's safety net for a webhook that crashed
    mid-processing (or whose handler failed) - re-fetches the event fresh
    from Stripe and reprocesses it. Each event gets its own try/except so
    one permanently broken event can't stall the batch (also capped by
    webhook_max_retry_attempts)."""
    threshold = datetime.now(UTC) - timedelta(minutes=settings.webhook_retry_after_minutes)
    async with AsyncSessionLocal() as db:
        stuck = await payments_repo.list_stuck_events(
            db,
            stuck_since=threshold,
            max_attempts=settings.webhook_max_retry_attempts,
            limit=_RETRY_BATCH_LIMIT,
        )
        retried = 0
        for webhook_row in stuck:
            try:
                await payments_service.reprocess_webhook_event(db, ctx["redis"], webhook_row)
                retried += 1
            except Exception:
                logger.exception("Retry failed for webhook event %s", webhook_row.stripe_event_id)
                await db.rollback()
        if stuck:
            logger.info("Retry swept %d stuck webhook events (%d succeeded)", len(stuck), retried)
