"""create bookings, booking_items, booking_payments, stripe_webhook_events

Revision ID: 8d4a1f2e6c93
Revises: 61433c7c8373
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum


# revision identifiers, used by Alembic.
revision: str = '8d4a1f2e6c93'
down_revision: Union[str, None] = '61433c7c8373'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _setting_value_type_column() -> PGEnum:
    return PGEnum('PERCENTAGE', 'FIXED', name='setting_value_type', create_type=False)


def _currency_column() -> PGEnum:
    return PGEnum('EUR', name='currency', create_type=False)


def _payment_schedule_column() -> PGEnum:
    return PGEnum('FULL_UPFRONT', 'DEPOSIT_THEN_BALANCE', name='payment_schedule', create_type=False)


def _booking_status_column() -> PGEnum:
    return PGEnum(
        'PENDING_PAYMENT', 'CONFIRMED', 'IN_PROGRESS', 'COMPLETED', 'NO_SHOW',
        'CANCELLED_BY_CUSTOMER', 'CANCELLED_BY_BRAIDER', 'CANCELLED_NO_PAYMENT',
        'EXPIRED', 'DISPUTED',
        name='booking_status', create_type=False,
    )


def _balance_charge_state_column() -> PGEnum:
    return PGEnum(
        'NOT_APPLICABLE', 'SCHEDULED', 'DUE', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED', 'ABANDONED',
        name='balance_charge_state', create_type=False,
    )


def _cancelled_by_column() -> PGEnum:
    return PGEnum('CUSTOMER', 'BRAIDER', 'SYSTEM', name='cancelled_by', create_type=False)


def _booking_item_type_column() -> PGEnum:
    return PGEnum(
        'SERVICE', 'VARIATION', 'ADDON', 'TRAVEL', 'PLATFORM_FEE', 'VAT_SERVICE', 'VAT_PLATFORM_FEE',
        name='booking_item_type', create_type=False,
    )


def _payment_purpose_column() -> PGEnum:
    return PGEnum('FULL', 'DEPOSIT', 'BALANCE', name='payment_purpose', create_type=False)


def _payment_status_column() -> PGEnum:
    return PGEnum('PENDING', 'SUCCEEDED', 'FAILED', 'CANCELED', name='payment_status', create_type=False)


def _webhook_event_source_column() -> PGEnum:
    return PGEnum('CONNECT', 'PAYMENTS', name='webhook_event_source', create_type=False)


def _webhook_event_status_column() -> PGEnum:
    return PGEnum('RECEIVED', 'PROCESSED', 'FAILED', 'IGNORED', name='webhook_event_status', create_type=False)


def upgrade() -> None:
    # Backs the ex_bookings_no_overlap exclusion constraint below - a plain
    # equality operator class (uuid =) needs the gist extension operator
    # classes to combine with the tstzrange && operator in one GIST index.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.execute("CREATE TYPE payment_schedule AS ENUM ('FULL_UPFRONT', 'DEPOSIT_THEN_BALANCE')")
    op.execute(
        "CREATE TYPE booking_status AS ENUM ("
        "'PENDING_PAYMENT', 'CONFIRMED', 'IN_PROGRESS', 'COMPLETED', 'NO_SHOW', "
        "'CANCELLED_BY_CUSTOMER', 'CANCELLED_BY_BRAIDER', 'CANCELLED_NO_PAYMENT', "
        "'EXPIRED', 'DISPUTED')"
    )
    op.execute(
        "CREATE TYPE balance_charge_state AS ENUM ("
        "'NOT_APPLICABLE', 'SCHEDULED', 'DUE', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED', 'ABANDONED')"
    )
    op.execute("CREATE TYPE cancelled_by AS ENUM ('CUSTOMER', 'BRAIDER', 'SYSTEM')")
    op.execute(
        "CREATE TYPE booking_item_type AS ENUM ("
        "'SERVICE', 'VARIATION', 'ADDON', 'TRAVEL', 'PLATFORM_FEE', 'VAT_SERVICE', 'VAT_PLATFORM_FEE')"
    )
    op.execute("CREATE TYPE payment_purpose AS ENUM ('FULL', 'DEPOSIT', 'BALANCE')")
    op.execute("CREATE TYPE payment_status AS ENUM ('PENDING', 'SUCCEEDED', 'FAILED', 'CANCELED')")
    op.execute("CREATE TYPE webhook_event_source AS ENUM ('CONNECT', 'PAYMENTS')")
    op.execute("CREATE TYPE webhook_event_status AS ENUM ('RECEIVED', 'PROCESSED', 'FAILED', 'IGNORED')")

    op.add_column('users', sa.Column('stripe_customer_id', sa.String(length=64), nullable=True))

    op.create_table(
        'bookings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('reference', sa.String(length=12), nullable=False),
        sa.Column('customer_id', sa.UUID(), nullable=False),
        sa.Column('braider_id', sa.UUID(), nullable=False),
        sa.Column('booking_calculation_id', sa.UUID(), nullable=False),
        sa.Column('braider_style_id', sa.UUID(), nullable=False),
        sa.Column('style_id', sa.UUID(), nullable=False),
        sa.Column('style_variation_id', sa.UUID(), nullable=True),
        sa.Column('braider_style_variation_id', sa.UUID(), nullable=True),
        sa.Column('is_mobile', sa.Boolean(), nullable=False),
        sa.Column('country', sa.String(length=2), nullable=False),
        sa.Column('client_address', sa.String(length=500), nullable=True),
        sa.Column('client_latitude', sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column('client_longitude', sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column('currency', _currency_column(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('braider_timezone', sa.String(length=64), nullable=False),
        sa.Column('blocked_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('blocked_until', sa.DateTime(timezone=True), nullable=False),
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
        sa.Column('payment_schedule', _payment_schedule_column(), nullable=False),
        sa.Column('braider_share_total', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('braider_share_deposit', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('braider_share_balance', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('status', _booking_status_column(), nullable=False),
        sa.Column('hold_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancellation_cutoff_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('balance_charge_due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('balance_charge_state', _balance_charge_state_column(), nullable=False),
        sa.Column('balance_charge_attempts', sa.Integer(), nullable=False),
        sa.Column('balance_charge_last_error', sa.String(length=500), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_by', _cancelled_by_column(), nullable=True),
        sa.Column('stripe_customer_id', sa.String(length=64), nullable=True),
        sa.Column('stripe_payment_method_id', sa.String(length=64), nullable=True),
        sa.Column('locale', sa.String(length=5), nullable=False),
        sa.Column('terms_version', sa.String(length=20), nullable=False),
        sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['braider_id'], ['braider_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['booking_calculation_id'], ['booking_calculations.id']),
        sa.ForeignKeyConstraint(['braider_style_id'], ['braider_styles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['style_id'], ['styles.id']),
        sa.ForeignKeyConstraint(['style_variation_id'], ['style_variations.id']),
        sa.CheckConstraint(
            "service_subtotal >= 0 AND travel_fee >= 0 AND subtotal >= 0 AND "
            "platform_fee_value >= 0 AND platform_fee >= 0 AND "
            "vat_service_value >= 0 AND vat_platform_fee_value >= 0 AND "
            "vat_on_service >= 0 AND vat_on_platform_fee >= 0 AND vat_total >= 0 AND "
            "total >= 0 AND deposit_value >= 0 AND deposit_amount >= 0 AND balance_amount >= 0 AND "
            "braider_share_total >= 0 AND braider_share_deposit >= 0 AND braider_share_balance >= 0 AND "
            "subtotal = service_subtotal + travel_fee AND "
            "total = subtotal + platform_fee + vat_total AND "
            "vat_total = vat_on_service + vat_on_platform_fee AND "
            "deposit_amount + balance_amount = total AND "
            "braider_share_deposit + braider_share_balance = braider_share_total AND "
            "ends_at > starts_at AND blocked_until > blocked_from",
            name='ck_bookings_amounts',
        ),
        sa.UniqueConstraint('reference', name='uq_bookings_reference'),
        sa.UniqueConstraint('booking_calculation_id', name='uq_bookings_booking_calculation_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bookings_customer_id', 'bookings', ['customer_id'])
    op.create_index('ix_bookings_braider_id', 'bookings', ['braider_id'])
    op.create_index('ix_bookings_starts_at', 'bookings', ['starts_at'])
    op.create_index('ix_bookings_blocked_until', 'bookings', ['blocked_until'])
    op.create_index('ix_bookings_status', 'bookings', ['status'])

    # Double-booking guard at the database level - the WHERE clause must
    # match app.modules.bookings.enums.CALENDAR_BLOCKING_STATUSES exactly.
    op.execute(
        "ALTER TABLE bookings ADD CONSTRAINT ex_bookings_no_overlap "
        "EXCLUDE USING gist (braider_id WITH =, "
        "tstzrange(blocked_from, blocked_until, '[)') WITH &&) "
        "WHERE (status IN ('PENDING_PAYMENT', 'CONFIRMED', 'IN_PROGRESS', 'COMPLETED', 'NO_SHOW', 'DISPUTED'))"
    )

    # Added now that bookings exists - booking_calculations predates it.
    op.create_foreign_key(
        'fk_booking_calculations_consumed_by_booking_id',
        'booking_calculations', 'bookings',
        ['consumed_by_booking_id'], ['id'],
    )

    op.create_table(
        'booking_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('booking_id', sa.UUID(), nullable=False),
        sa.Column('item_type', _booking_item_type_column(), nullable=False),
        sa.Column('name_en', sa.String(length=255), nullable=True),
        sa.Column('name_de', sa.String(length=255), nullable=True),
        sa.Column('name_fr', sa.String(length=255), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('line_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False),
        sa.Column('vat_rate', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('source_style_id', sa.UUID(), nullable=True),
        sa.Column('source_style_variation_id', sa.UUID(), nullable=True),
        sa.Column('source_addon_id', sa.UUID(), nullable=True),
        sa.Column('source_braider_style_addon_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.CheckConstraint(
            'quantity > 0 AND unit_amount >= 0 AND line_amount >= 0', name='ck_booking_items_amounts'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_booking_items_booking_id', 'booking_items', ['booking_id'])

    op.create_table(
        'booking_payments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('booking_id', sa.UUID(), nullable=False),
        sa.Column('purpose', _payment_purpose_column(), nullable=False),
        sa.Column('status', _payment_status_column(), nullable=False),
        sa.Column('amount_minor', sa.BigInteger(), nullable=False),
        sa.Column('currency', _currency_column(), nullable=False),
        sa.Column('braider_share_minor', sa.BigInteger(), nullable=False),
        sa.Column('amount_refunded_minor', sa.BigInteger(), nullable=False),
        sa.Column('amount_transferred_minor', sa.BigInteger(), nullable=False),
        sa.Column('stripe_payment_intent_id', sa.String(length=64), nullable=True),
        sa.Column('stripe_charge_id', sa.String(length=64), nullable=True),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('is_off_session', sa.Boolean(), nullable=False),
        sa.Column('transfer_group', sa.String(length=64), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('failure_code', sa.String(length=100), nullable=True),
        sa.Column('failure_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.CheckConstraint(
            "amount_minor >= 0 AND braider_share_minor >= 0 AND "
            "amount_refunded_minor >= 0 AND amount_transferred_minor >= 0 AND attempt_number > 0",
            name='ck_booking_payments_amounts',
        ),
        sa.UniqueConstraint('idempotency_key', name='uq_booking_payments_idempotency_key'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_booking_payments_booking_id', 'booking_payments', ['booking_id'])
    op.create_index(
        'ix_booking_payments_stripe_payment_intent_id', 'booking_payments', ['stripe_payment_intent_id']
    )
    # Partial (not plain) unique - at most one SUCCEEDED payment per
    # (booking, purpose), while failed retries persist as history.
    op.execute(
        "CREATE UNIQUE INDEX uq_booking_payment_succeeded ON booking_payments (booking_id, purpose) "
        "WHERE status = 'SUCCEEDED'"
    )

    op.create_table(
        'stripe_webhook_events',
        sa.Column('stripe_event_id', sa.String(length=255), nullable=False),
        sa.Column('source', _webhook_event_source_column(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('status', _webhook_event_status_column(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('payload', sa.Text(), nullable=True),
        sa.Column('last_error', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('stripe_event_id'),
    )


def downgrade() -> None:
    op.drop_table('stripe_webhook_events')

    op.execute('DROP INDEX IF EXISTS uq_booking_payment_succeeded')
    op.drop_index('ix_booking_payments_stripe_payment_intent_id', table_name='booking_payments')
    op.drop_index('ix_booking_payments_booking_id', table_name='booking_payments')
    op.drop_table('booking_payments')

    op.drop_index('ix_booking_items_booking_id', table_name='booking_items')
    op.drop_table('booking_items')

    op.drop_constraint(
        'fk_booking_calculations_consumed_by_booking_id', 'booking_calculations', type_='foreignkey'
    )
    op.execute('ALTER TABLE bookings DROP CONSTRAINT IF EXISTS ex_bookings_no_overlap')
    op.drop_index('ix_bookings_status', table_name='bookings')
    op.drop_index('ix_bookings_blocked_until', table_name='bookings')
    op.drop_index('ix_bookings_starts_at', table_name='bookings')
    op.drop_index('ix_bookings_braider_id', table_name='bookings')
    op.drop_index('ix_bookings_customer_id', table_name='bookings')
    op.drop_table('bookings')

    op.drop_column('users', 'stripe_customer_id')

    sa.Enum(name='webhook_event_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='webhook_event_source').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='payment_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='payment_purpose').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='booking_item_type').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='cancelled_by').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='balance_charge_state').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='booking_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='payment_schedule').drop(op.get_bind(), checkfirst=True)

    op.execute('DROP EXTENSION IF EXISTS btree_gist')
