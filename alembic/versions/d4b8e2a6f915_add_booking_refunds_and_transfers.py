"""add booking refunds, transfers, and cancellation_reason

Revision ID: d4b8e2a6f915
Revises: c2f6a9d3e7b1
Create Date: 2026-08-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum


# revision identifiers, used by Alembic.
revision: str = 'd4b8e2a6f915'
down_revision: Union[str, None] = 'c2f6a9d3e7b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _currency_column() -> PGEnum:
    return PGEnum('EUR', name='currency', create_type=False)


def _refund_status_column() -> PGEnum:
    return PGEnum('PENDING', 'SUCCEEDED', 'FAILED', name='refund_status', create_type=False)


def _transfer_status_column() -> PGEnum:
    return PGEnum('PENDING', 'SUCCEEDED', 'FAILED', 'REVERSED', name='transfer_status', create_type=False)


def upgrade() -> None:
    op.add_column('bookings', sa.Column('cancellation_reason', sa.Text(), nullable=True))

    op.execute("CREATE TYPE refund_status AS ENUM ('PENDING', 'SUCCEEDED', 'FAILED')")
    op.execute("CREATE TYPE transfer_status AS ENUM ('PENDING', 'SUCCEEDED', 'FAILED', 'REVERSED')")

    op.create_table(
        'booking_refunds',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('booking_id', sa.UUID(), nullable=False),
        sa.Column('booking_payment_id', sa.UUID(), nullable=False),
        sa.Column('status', _refund_status_column(), nullable=False),
        sa.Column('amount_minor', sa.BigInteger(), nullable=False),
        sa.Column('currency', _currency_column(), nullable=False),
        sa.Column('stripe_refund_id', sa.String(length=64), nullable=True),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('failure_code', sa.String(length=100), nullable=True),
        sa.Column('failure_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['booking_payment_id'], ['booking_payments.id'], ondelete='CASCADE'),
        sa.CheckConstraint('amount_minor > 0', name='ck_booking_refunds_amount'),
        sa.UniqueConstraint('idempotency_key', name='uq_booking_refunds_idempotency_key'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_booking_refunds_booking_id', 'booking_refunds', ['booking_id'])
    op.create_index('ix_booking_refunds_booking_payment_id', 'booking_refunds', ['booking_payment_id'])

    op.create_table(
        'booking_transfers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('booking_id', sa.UUID(), nullable=False),
        sa.Column('booking_payment_id', sa.UUID(), nullable=False),
        sa.Column('destination_account_id', sa.String(length=64), nullable=False),
        sa.Column('status', _transfer_status_column(), nullable=False),
        sa.Column('amount_minor', sa.BigInteger(), nullable=False),
        sa.Column('currency', _currency_column(), nullable=False),
        sa.Column('transfer_group', sa.String(length=64), nullable=False),
        sa.Column('stripe_transfer_id', sa.String(length=64), nullable=True),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('failure_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['booking_payment_id'], ['booking_payments.id'], ondelete='CASCADE'),
        sa.CheckConstraint('amount_minor > 0', name='ck_booking_transfers_amount'),
        sa.UniqueConstraint('idempotency_key', name='uq_booking_transfers_idempotency_key'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_booking_transfers_booking_id', 'booking_transfers', ['booking_id'])
    op.create_index('ix_booking_transfers_booking_payment_id', 'booking_transfers', ['booking_payment_id'])
    # At most one PENDING/SUCCEEDED transfer per payment - a REVERSED one
    # doesn't free the slot for reuse, a brand new transfer would need its
    # own row (see the model docstring).
    op.execute(
        "CREATE UNIQUE INDEX uq_booking_transfers_active_per_payment ON booking_transfers (booking_payment_id) "
        "WHERE status IN ('PENDING', 'SUCCEEDED')"
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS uq_booking_transfers_active_per_payment')
    op.drop_index('ix_booking_transfers_booking_payment_id', table_name='booking_transfers')
    op.drop_index('ix_booking_transfers_booking_id', table_name='booking_transfers')
    op.drop_table('booking_transfers')

    op.drop_index('ix_booking_refunds_booking_payment_id', table_name='booking_refunds')
    op.drop_index('ix_booking_refunds_booking_id', table_name='booking_refunds')
    op.drop_table('booking_refunds')

    sa.Enum(name='transfer_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='refund_status').drop(op.get_bind(), checkfirst=True)

    op.drop_column('bookings', 'cancellation_reason')
