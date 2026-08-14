from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.enums import WebhookEventSource, WebhookEventStatus
from app.modules.bookings.payments.models import StripeWebhookEvent


async def get_by_event_id(db: AsyncSession, stripe_event_id: str) -> StripeWebhookEvent | None:
    return await db.get(StripeWebhookEvent, stripe_event_id)


async def list_stuck_events(
    db: AsyncSession, *, stuck_since: datetime, max_attempts: int, limit: int
) -> list[StripeWebhookEvent]:
    """retry_webhook_events_cron's target set - FAILED events (the
    handler raised) or ones stuck at RECEIVED past stuck_since (processing
    crashed between insert-first and mark_processed/mark_failed - design
    correction #7). Scoped to the PAYMENTS source; Connect events aren't
    part of this reconciliation. Capped by max_attempts so a permanently
    broken event doesn't retry forever."""
    result = await db.execute(
        select(StripeWebhookEvent)
        .where(
            StripeWebhookEvent.source == WebhookEventSource.PAYMENTS,
            StripeWebhookEvent.attempts < max_attempts,
            or_(
                StripeWebhookEvent.status == WebhookEventStatus.FAILED,
                and_(
                    StripeWebhookEvent.status == WebhookEventStatus.RECEIVED,
                    StripeWebhookEvent.created_at <= stuck_since,
                ),
            ),
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def increment_attempts(db: AsyncSession, event: StripeWebhookEvent) -> None:
    event.attempts += 1
    await db.flush()


async def create_received(
    db: AsyncSession,
    *,
    stripe_event_id: str,
    source: WebhookEventSource,
    event_type: str,
    payload: str,
) -> StripeWebhookEvent:
    row = StripeWebhookEvent(
        stripe_event_id=stripe_event_id,
        source=source,
        event_type=event_type,
        status=WebhookEventStatus.RECEIVED,
        payload=payload,
    )
    db.add(row)
    await db.flush()
    return row


async def mark_processed(db: AsyncSession, event: StripeWebhookEvent) -> None:
    event.status = WebhookEventStatus.PROCESSED
    event.processed_at = datetime.now(UTC)
    await db.flush()


async def mark_ignored(db: AsyncSession, event: StripeWebhookEvent) -> None:
    event.status = WebhookEventStatus.IGNORED
    event.processed_at = datetime.now(UTC)
    await db.flush()


async def mark_failed(db: AsyncSession, event: StripeWebhookEvent, *, error: str) -> None:
    event.status = WebhookEventStatus.FAILED
    event.last_error = error[:500]
    await db.flush()
