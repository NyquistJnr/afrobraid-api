"""add receipts, receipt_counters, and braider vat snapshot on bookings

Revision ID: a3d7e5f0c2b8
Revises: f2a9c6d1b4e7
Create Date: 2026-08-14 00:00:00.000003

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum


# revision identifiers, used by Alembic.
revision: str = 'a3d7e5f0c2b8'
down_revision: Union[str, None] = 'f2a9c6d1b4e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _currency_column() -> PGEnum:
    return PGEnum('EUR', name='currency', create_type=False)


def _braider_vat_status_column() -> PGEnum:
    return PGEnum('UNKNOWN', 'STANDARD', 'SMALL_BUSINESS', name='braider_vat_status', create_type=False)


def _receipt_type_column() -> PGEnum:
    return PGEnum('INVOICE', 'CREDIT_NOTE', name='receipt_type', create_type=False)


def upgrade() -> None:
    op.execute("CREATE TYPE braider_vat_status AS ENUM ('UNKNOWN', 'STANDARD', 'SMALL_BUSINESS')")
    op.execute("CREATE TYPE receipt_type AS ENUM ('INVOICE', 'CREDIT_NOTE')")

    op.add_column(
        'bookings',
        sa.Column(
            'braider_vat_status', _braider_vat_status_column(), nullable=False, server_default='UNKNOWN'
        ),
    )
    op.alter_column('bookings', 'braider_vat_status', server_default=None)
    op.add_column('bookings', sa.Column('braider_vat_number', sa.String(length=32), nullable=True))

    op.create_table(
        'receipt_counters',
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('last_number', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('year'),
    )
    op.alter_column('receipt_counters', 'last_number', server_default=None)

    op.create_table(
        'receipts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('booking_id', sa.UUID(), nullable=False),
        sa.Column('booking_payment_id', sa.UUID(), nullable=False),
        sa.Column('booking_refund_id', sa.UUID(), nullable=True),
        sa.Column('credit_note_for_receipt_id', sa.UUID(), nullable=True),
        sa.Column('type', _receipt_type_column(), nullable=False),
        sa.Column('receipt_number', sa.String(length=20), nullable=False),
        sa.Column('public_token', sa.String(length=64), nullable=False),
        sa.Column('locale', sa.String(length=5), nullable=False),
        sa.Column('amount_total', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            'prior_receipts_total', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'
        ),
        sa.Column('currency', _currency_column(), nullable=False),
        sa.Column('braider_vat_status', _braider_vat_status_column(), nullable=False),
        sa.Column('braider_vat_number', sa.String(length=32), nullable=True),
        sa.Column('html', sa.Text(), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['booking_payment_id'], ['booking_payments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['booking_refund_id'], ['booking_refunds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['credit_note_for_receipt_id'], ['receipts.id']),
        sa.CheckConstraint(
            'amount_total >= 0 AND prior_receipts_total >= 0', name='ck_receipts_amounts'
        ),
        sa.UniqueConstraint('receipt_number', name='uq_receipts_receipt_number'),
        sa.UniqueConstraint('public_token', name='uq_receipts_public_token'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('receipts', 'prior_receipts_total', server_default=None)
    op.create_index('ix_receipts_booking_id', 'receipts', ['booking_id'])
    op.create_index('ix_receipts_booking_payment_id', 'receipts', ['booking_payment_id'])


def downgrade() -> None:
    op.drop_index('ix_receipts_booking_payment_id', table_name='receipts')
    op.drop_index('ix_receipts_booking_id', table_name='receipts')
    op.drop_table('receipts')
    op.drop_table('receipt_counters')

    op.drop_column('bookings', 'braider_vat_number')
    op.drop_column('bookings', 'braider_vat_status')

    sa.Enum(name='receipt_type').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='braider_vat_status').drop(op.get_bind(), checkfirst=True)
