import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StripeConnectAccount(Base):
    __tablename__ = "stripe_connect_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    braider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("braider_profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    stripe_account_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    charges_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payouts_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    details_submitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    disabled_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # JSON-encoded list of Stripe's `requirements.currently_due` strings, so
    # the braider can see exactly what's still missing on their own dashboard.
    requirements_currently_due: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_webhook_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
