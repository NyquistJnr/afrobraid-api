import logging

from app.core.database import AsyncSessionLocal
from app.modules.bookings.calculations import repository as calculations_repo

logger = logging.getLogger("app.cron.booking_calculations")

_CLEANUP_BATCH_LIMIT = 5000


async def expire_booking_calculations_cron(ctx: dict) -> None:
    """Deletes expired DRAFT booking_calculations in batches - runs hourly,
    well ahead of the 2h TTL, so the table never accumulates a large
    abandoned-quote backlog. Own DB session per the repo's task convention
    (see app.worker)."""
    async with AsyncSessionLocal() as db:
        deleted = await calculations_repo.delete_expired_draft_calculations(
            db, limit=_CLEANUP_BATCH_LIMIT
        )
        await db.commit()
        if deleted:
            logger.info("Deleted %d expired DRAFT booking calculations", deleted)
