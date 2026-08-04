import logging
from typing import Annotated

import stripe
from arq import ArqRedis
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.core.queue import get_task_queue
from app.modules.bookings.models import BookingPayment, StripeWebhookEvent, Booking
from app.modules.bookings.enums import PaymentStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/stripe/platform", tags=["Webhooks"])


@router.post("/", include_in_schema=False)
async def platform_webhook(
    request: Request,
    stripe_signature: Annotated[str, Header()],
    db: Annotated[AsyncSession, Depends(get_db)],
    queue: Annotated[ArqRedis, Depends(get_task_queue)],
):
    payload = await request.body()
    webhook_secret = get_settings().stripe_payments_webhook_secret
    if not webhook_secret:
        logger.warning("stripe_payments_webhook_secret not configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload, sig_header=stripe_signature, secret=webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 1. Deduplication using StripeWebhookEvent
    event_id = event["id"]
    stmt = select(StripeWebhookEvent).where(StripeWebhookEvent.stripe_event_id == event_id)
    db_event = (await db.execute(stmt)).scalar_one_or_none()

    if db_event:
        if db_event.status == "PROCESSED":
            return {"status": "already_processed"}
        db_event.attempts += 1
    else:
        db_event = StripeWebhookEvent(
            stripe_event_id=event_id,
            source="platform",
            status="RECEIVED",
            attempts=1,
        )
        db.add(db_event)
        
    await db.flush()

    # 2. Process event
    try:
        if event["type"] == "payment_intent.succeeded":
            payment_intent = event["data"]["object"]
            pi_id = payment_intent["id"]
            
            # Find the booking payment
            payment_stmt = (
                select(BookingPayment)
                .where(BookingPayment.stripe_payment_intent_id == pi_id)
                .options(
                    selectinload(BookingPayment.booking).selectinload(Booking.customer)
                )
            )
            payment = (await db.execute(payment_stmt)).scalar_one_or_none()
            if payment and payment.status != PaymentStatus.SUCCEEDED:
                payment.status = PaymentStatus.SUCCEEDED
                payment.stripe_charge_id = payment_intent.get("latest_charge")
                
                # Update booking status (simplified)
                from app.modules.bookings.enums import BookingStatus
                if payment.booking.status == BookingStatus.PENDING_PAYMENT:
                    payment.booking.status = BookingStatus.CONFIRMED
                    
                    # Send confirmation email
                    await queue.enqueue_job(
                        "send_email",
                        to=payment.booking.customer.email,
                        subject=f"Booking Confirmed: {payment.booking.reference}",
                        html=f"<p>Your booking {payment.booking.reference} is confirmed!</p>",
                    )

        db_event.status = "PROCESSED"
        await db.commit()
    except Exception as e:
        logger.error(f"Error processing platform webhook: {e}")
        db_event.status = "FAILED"
        await db.commit()
        raise HTTPException(status_code=500, detail="Internal server error")

    return {"status": "success"}
