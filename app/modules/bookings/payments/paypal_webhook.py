import logging

from arq import ArqRedis
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import PaypalInvalidWebhookSignatureError
from app.core.queue import get_task_queue
from app.modules.bookings.payments import service
from app.modules.bookings.payments.paypal_client import (
    PaypalWebhookSignatureError,
    construct_webhook_event,
)

logger = logging.getLogger("app.webhooks.paypal.payments")

router = APIRouter(
    prefix="/api/v1/webhooks/paypal/payments",
    tags=["Webhooks - PayPal Payments"],
    include_in_schema=False,
)


@router.post("")
async def paypal_payments_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> dict[str, str]:
    raw_body = await request.body()

    try:
        event = await construct_webhook_event(dict(request.headers), raw_body)
    except PaypalWebhookSignatureError as exc:
        raise PaypalInvalidWebhookSignatureError() from exc

    await service.handle_paypal_webhook_event(db, queue, event=event)
    return {"status": "ok"}
