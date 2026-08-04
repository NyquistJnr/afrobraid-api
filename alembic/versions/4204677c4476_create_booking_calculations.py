"""create booking calculations

Revision ID: 4204677c4476
Revises: 74a29faaffdb
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum


# revision identifiers, used by Alembic.
revision: str = '4204677c4476'
down_revision: Union[str, None] = '74a29faaffdb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _setting_value_type_column() -> PGEnum:
    # Already created (raw SQL) by 9a4f2c6e8d1b - reused here, create_type=False.
    return PGEnum('PERCENTAGE', 'FIXED', name='setting_value_type', create_type=False)


def _currency_column() -> PGEnum:
    return PGEnum('EUR', name='currency', create_type=False)


def _booking_calculation_status_column() -> PGEnum:
    return PGEnum('DRAFT', 'CONSUMED', 'EXPIRED', name='booking_calculation_status', create_type=False)


def upgrade() -> None:
    op.execute("CREATE TYPE currency AS ENUM ('EUR')")
    op.execute("CREATE TYPE booking_calculation_status AS ENUM ('DRAFT', 'CONSUMED', 'EXPIRED')")

    op.create_table(
        'booking_calculations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('braider_id', sa.UUID(), nullable=False),
        sa.Column('braider_style_id', sa.UUID(), nullable=False),
        sa.Column('style_id', sa.UUID(), nullable=False),
        sa.Column('style_variation_id', sa.UUID(), nullable=True),
        sa.Column('braider_style_variation_id', sa.UUID(), nullable=True),
        sa.Column('is_mobile', sa.Boolean(), nullable=False),
        sa.Column('currency', _currency_column(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('service_subtotal', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('travel_fee', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('platform_fee_type', _setting_value_type_column(), nullable=False),
        sa.Column('platform_fee_value', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('platform_fee', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('vat_service_type', _setting_value_type_column(), nullable=False),
        sa.Column('vat_service_value', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('vat_on_service', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('vat_platform_fee_type', _setting_value_type_column(), nullable=False),
        sa.Column('vat_platform_fee_value', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('vat_on_platform_fee', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('vat_total', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('total', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('deposit_type', _setting_value_type_column(), nullable=False),
        sa.Column('deposit_value', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('deposit_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('balance_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('status', _booking_calculation_status_column(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_by_booking_id', sa.UUID(), nullable=True),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('client_ip_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['braider_id'], ['braider_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['braider_style_id'], ['braider_styles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['style_id'], ['styles.id']),
        sa.ForeignKeyConstraint(['style_variation_id'], ['style_variations.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint(
            "service_subtotal >= 0 AND travel_fee >= 0 AND subtotal >= 0 AND "
            "platform_fee_value >= 0 AND platform_fee >= 0 AND "
            "vat_service_value >= 0 AND vat_platform_fee_value >= 0 AND "
            "vat_on_service >= 0 AND vat_on_platform_fee >= 0 AND vat_total >= 0 AND "
            "total >= 0 AND deposit_value >= 0 AND deposit_amount >= 0 AND balance_amount >= 0 AND "
            "subtotal = service_subtotal + travel_fee AND "
            "total = subtotal + platform_fee + vat_total AND "
            "vat_total = vat_on_service + vat_on_platform_fee AND "
            "deposit_amount + balance_amount = total",
            name='ck_booking_calculations_amounts',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_booking_calculations_braider_id', 'booking_calculations', ['braider_id']
    )
    op.create_index(
        'ix_booking_calculations_braider_style_id', 'booking_calculations', ['braider_style_id']
    )
    op.create_index('ix_booking_calculations_status', 'booking_calculations', ['status'])
    op.create_index('ix_booking_calculations_expires_at', 'booking_calculations', ['expires_at'])
    # Partial index backing the cleanup cron's WHERE status='DRAFT' AND
    # expires_at < now() query - not expressible via the ORM's plain Index(),
    # so added here as raw SQL (same approach as this repo's other
    # exotic/partial indexes and constraints).
    op.execute(
        "CREATE INDEX ix_booking_calculations_cleanup ON booking_calculations (expires_at) "
        "WHERE status = 'DRAFT'"
    )

    op.create_table(
        'booking_calculation_addons',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('booking_calculation_id', sa.UUID(), nullable=False),
        sa.Column('braider_style_addon_id', sa.UUID(), nullable=False),
        sa.Column('addon_id', sa.UUID(), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['booking_calculation_id'], ['booking_calculations.id'], ondelete='CASCADE'
        ),
        sa.CheckConstraint('price >= 0', name='ck_booking_calculation_addons_price'),
        sa.UniqueConstraint(
            'booking_calculation_id', 'braider_style_addon_id', name='uq_booking_calculation_addon'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_booking_calculation_addons_booking_calculation_id',
        'booking_calculation_addons',
        ['booking_calculation_id'],
    )


def downgrade() -> None:
    op.drop_table('booking_calculation_addons')
    op.drop_index('ix_booking_calculations_cleanup', table_name='booking_calculations')
    op.drop_index('ix_booking_calculations_expires_at', table_name='booking_calculations')
    op.drop_index('ix_booking_calculations_status', table_name='booking_calculations')
    op.drop_index('ix_booking_calculations_braider_style_id', table_name='booking_calculations')
    op.drop_index('ix_booking_calculations_braider_id', table_name='booking_calculations')
    op.drop_table('booking_calculations')
    sa.Enum(name='booking_calculation_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='currency').drop(op.get_bind(), checkfirst=True)
