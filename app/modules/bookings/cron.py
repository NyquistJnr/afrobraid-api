import logging

from app.core.database import AsyncSessionLocal
from app.modules.bookings import repository as bookings_repo

logger = logging.getLogger("app.cron.bookings")

_EXPIRE_BATCH_LIMIT = 5000


async def expire_booking_holds_cron(ctx: dict) -> None:
    """Releases a PENDING_PAYMENT booking's calendar hold once its
    hold_expires_at has passed with no successful payment - runs every
    minute, matching the plan's `expire_booking_holds` cron."""
    async with AsyncSessionLocal() as db:
        expired = await bookings_repo.expire_stale_holds(db, limit=_EXPIRE_BATCH_LIMIT)
        await db.commit()
        if expired:
            logger.info("Expired %d stale PENDING_PAYMENT booking holds", expired)
