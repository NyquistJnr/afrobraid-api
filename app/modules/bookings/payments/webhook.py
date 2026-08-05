import logging

from arq import ArqRedis
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import StripeInvalidWebhookSignatureError
from app.core.queue import get_task_queue
from app.modules.bookings.enums import WebhookEventSource
from app.modules.bookings.payments import service
from app.modules.bookings.payments.client import (
    StripeWebhookSignatureError,
    construct_payments_webhook_event,
)

logger = logging.getLogger("app.webhooks.stripe.payments")

router = APIRouter(
    prefix="/api/v1/webhooks/stripe/payments",
    tags=["Webhooks - Stripe Payments"],
    include_in_schema=False,
)


@router.post("")
async def stripe_payments_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> dict[str, str]:
    raw_body = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = construct_payments_webhook_event(raw_body, sig_header)
    except StripeWebhookSignatureError as exc:
        raise StripeInvalidWebhookSignatureError() from exc

    await service.handle_webhook_event(db, queue, event=event, source=WebhookEventSource.PAYMENTS)
    return {"status": "ok"}
