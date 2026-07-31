import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import StripeInvalidWebhookSignatureError
from app.modules.braiders.payment_setup import service
from app.modules.braiders.payment_setup.client import (
    StripeWebhookSignatureError,
    construct_webhook_event,
)

logger = logging.getLogger("app.webhooks.stripe")

router = APIRouter(
    prefix="/api/v1/webhooks/stripe", tags=["Webhooks - Stripe"], include_in_schema=False
)


@router.post("")
async def stripe_account_webhook(
    request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    raw_body = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = construct_webhook_event(raw_body, sig_header)
    except StripeWebhookSignatureError as exc:
        raise StripeInvalidWebhookSignatureError() from exc

    await service.handle_webhook(db, event)
    return {"status": "ok"}
