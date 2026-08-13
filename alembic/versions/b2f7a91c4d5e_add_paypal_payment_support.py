"""add paypal payment support

Revision ID: b2f7a91c4d5e
Revises: aa4f0e29c18b
Create Date: 2026-08-13 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2f7a91c4d5e"
down_revision: str | None = "aa4f0e29c18b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

payment_provider = sa.Enum("STRIPE", "PAYPAL", name="payment_provider")

webhook_event_status = PGEnum(
    "RECEIVED", "PROCESSED", "FAILED", "IGNORED", name="webhook_event_status", create_type=False
)


def upgrade() -> None:
    payment_provider.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "booking_payments",
        sa.Column("provider", payment_provider, nullable=False, server_default="STRIPE"),
    )
    op.alter_column("booking_payments", "provider", server_default=None)

    op.add_column("booking_payments", sa.Column("paypal_order_id", sa.String(length=64), nullable=True))
    op.add_column("booking_payments", sa.Column("paypal_capture_id", sa.String(length=64), nullable=True))
    op.create_index("ix_booking_payments_paypal_order_id", "booking_payments", ["paypal_order_id"])

    op.create_table(
        "paypal_webhook_events",
        sa.Column("paypal_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("status", webhook_event_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("paypal_event_id"),
    )


def downgrade() -> None:
    op.drop_table("paypal_webhook_events")

    op.drop_index("ix_booking_payments_paypal_order_id", table_name="booking_payments")
    op.drop_column("booking_payments", "paypal_capture_id")
    op.drop_column("booking_payments", "paypal_order_id")
    op.drop_column("booking_payments", "provider")

    payment_provider.drop(op.get_bind(), checkfirst=True)
