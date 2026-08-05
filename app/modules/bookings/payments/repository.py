from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.enums import WebhookEventSource, WebhookEventStatus
from app.modules.bookings.payments.models import StripeWebhookEvent


async def get_by_event_id(db: AsyncSession, stripe_event_id: str) -> StripeWebhookEvent | None:
    return await db.get(StripeWebhookEvent, stripe_event_id)


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
