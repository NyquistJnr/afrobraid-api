"""add payout release, dispute fields, and transfer reversals

Revision ID: f2a9c6d1b4e7
Revises: e7c1a4f8b0d3
Create Date: 2026-08-14 00:00:00.000002

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum


# revision identifiers, used by Alembic.
revision: str = 'f2a9c6d1b4e7'
down_revision: Union[str, None] = 'e7c1a4f8b0d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _currency_column() -> PGEnum:
    return PGEnum('EUR', name='currency', create_type=False)


def _transfer_status_column() -> PGEnum:
    return PGEnum('PENDING', 'SUCCEEDED', 'FAILED', 'REVERSED', name='transfer_status', create_type=False)


def upgrade() -> None:
    op.add_column('bookings', sa.Column('stripe_dispute_id', sa.String(length=64), nullable=True))
    op.add_column('bookings', sa.Column('disputed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        'bookings',
        sa.Column('payouts_frozen', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('bookings', 'payouts_frozen', server_default=None)

    # Alembic autogenerate doesn't reliably detect Postgres enum VALUE
    # insertions - same convention as 707d295350ed_add_notification_types.py.
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'BOOKING_DISPUTED'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'PAYOUT_RELEASED'")

    op.create_table(
        'booking_transfer_reversals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('booking_id', sa.UUID(), nullable=False),
        sa.Column('booking_transfer_id', sa.UUID(), nullable=False),
        sa.Column('status', _transfer_status_column(), nullable=False),
        sa.Column('amount_minor', sa.BigInteger(), nullable=False),
        sa.Column('currency', _currency_column(), nullable=False),
        sa.Column('stripe_reversal_id', sa.String(length=64), nullable=True),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('failure_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['booking_transfer_id'], ['booking_transfers.id'], ondelete='CASCADE'),
        sa.CheckConstraint('amount_minor > 0', name='ck_booking_transfer_reversals_amount'),
        sa.UniqueConstraint('idempotency_key', name='uq_booking_transfer_reversals_idempotency_key'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_booking_transfer_reversals_booking_id', 'booking_transfer_reversals', ['booking_id']
    )
    op.create_index(
        'ix_booking_transfer_reversals_booking_transfer_id',
        'booking_transfer_reversals',
        ['booking_transfer_id'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_booking_transfer_reversals_booking_transfer_id', table_name='booking_transfer_reversals'
    )
    op.drop_index('ix_booking_transfer_reversals_booking_id', table_name='booking_transfer_reversals')
    op.drop_table('booking_transfer_reversals')

    op.drop_column('bookings', 'payouts_frozen')
    op.drop_column('bookings', 'disputed_at')
    op.drop_column('bookings', 'stripe_dispute_id')
