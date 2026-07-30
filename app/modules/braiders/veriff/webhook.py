import json
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import InvalidWebhookSignatureError
from app.modules.braiders.veriff import service
from app.modules.braiders.veriff.client import verify_signature

logger = logging.getLogger("app.webhooks.veriff")

router = APIRouter(
    prefix="/api/v1/webhooks/veriff", tags=["Webhooks - Veriff"], include_in_schema=False
)


@router.post("")
async def veriff_decision_webhook(
    request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    raw_body = await request.body()
    signature = request.headers.get("X-HMAC-SIGNATURE")
    if not verify_signature(raw_body, signature):
        raise InvalidWebhookSignatureError()

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.warning("Received Veriff webhook with invalid JSON body")
        return {"status": "ignored"}

    await service.handle_webhook(db, payload)
    return {"status": "ok"}
