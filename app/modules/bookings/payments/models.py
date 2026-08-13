from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.bookings.enums import WebhookEventSource, WebhookEventStatus


class StripeWebhookEvent(Base):
    """Insert-first dedupe record for every Stripe webhook delivery (both
    the Connect `account.updated` stream and this platform account's
    `payment_intent.*` stream - see `source`). Insert-first only stops
    *duplicate* delivery; it is not durability on its own (design correction
    #7) - `status` tracks RECEIVED -> PROCESSED/FAILED/IGNORED rather than
    the handler committing-and-forgetting, so a `reconcile_stripe_payments`
    sweep (Phase 7) can find and retry anything stuck at RECEIVED."""

    __tablename__ = "stripe_webhook_events"

    stripe_event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    source: Mapped[WebhookEventSource] = mapped_column(
        Enum(WebhookEventSource, name="webhook_event_source"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[WebhookEventStatus] = mapped_column(
        Enum(WebhookEventStatus, name="webhook_event_status"),
        nullable=False,
        default=WebhookEventStatus.RECEIVED,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PaypalWebhookEvent(Base):
    """Insert-first dedupe record for every PayPal webhook delivery on the
    booking checkout stream (PAYMENT.CAPTURE.* events) - same shape and same
    purpose as `StripeWebhookEvent` above. This is a reconciliation safety
    net, not the primary success path: the capture endpoint
    (`service.capture_paypal_payment`) finalizes the payment synchronously
    when the customer approves, so a redelivered or late-arriving webhook
    here is expected to find the payment already SUCCEEDED and no-op."""

    __tablename__ = "paypal_webhook_events"

    paypal_event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[WebhookEventStatus] = mapped_column(
        Enum(WebhookEventStatus, name="webhook_event_status"),
        nullable=False,
        default=WebhookEventStatus.RECEIVED,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
