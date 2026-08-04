"""add deposit and platform-fee VAT to platform settings

Revision ID: 74a29faaffdb
Revises: 9a4f2c6e8d1b
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum


# revision identifiers, used by Alembic.
revision: str = '74a29faaffdb'
down_revision: Union[str, None] = '9a4f2c6e8d1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_CHECK_SQL = (
    "platform_fee_value >= 0 AND vat_value >= 0 AND "
    "(platform_fee_type != 'PERCENTAGE' OR platform_fee_value <= 100) AND "
    "(vat_type != 'PERCENTAGE' OR vat_value <= 100)"
)

_NEW_CHECK_SQL = (
    "platform_fee_value >= 0 AND vat_value >= 0 AND "
    "vat_platform_fee_value >= 0 AND deposit_value >= 0 AND "
    "(platform_fee_type != 'PERCENTAGE' OR platform_fee_value <= 100) AND "
    "(vat_type != 'PERCENTAGE' OR vat_value <= 100) AND "
    "(vat_platform_fee_type != 'PERCENTAGE' OR vat_platform_fee_value <= 100) AND "
    "(deposit_type != 'PERCENTAGE' OR deposit_value <= 100)"
)


def _setting_value_type_column() -> PGEnum:
    # The 'setting_value_type' enum was already created (raw SQL) by
    # 9a4f2c6e8d1b - every new column referencing it must use
    # create_type=False, same idiom as that migration and 0e6486dca8e9.
    return PGEnum('PERCENTAGE', 'FIXED', name='setting_value_type', create_type=False)


def upgrade() -> None:
    # Nullable first - the singleton row (if it already exists in a
    # deployed environment) has no value for these yet.
    op.add_column(
        'platform_settings',
        sa.Column('vat_platform_fee_type', _setting_value_type_column(), nullable=True),
    )
    op.add_column(
        'platform_settings',
        sa.Column('vat_platform_fee_value', sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        'platform_settings',
        sa.Column('deposit_type', _setting_value_type_column(), nullable=True),
    )
    op.add_column(
        'platform_settings',
        sa.Column('deposit_value', sa.Numeric(precision=10, scale=2), nullable=True),
    )

    # Backfill the singleton row with the same defaults the service layer
    # seeds a brand-new row with (service.py: _DEFAULT_VAT_PLATFORM_FEE_*,
    # _DEFAULT_DEPOSIT_*). Mirrors the existing 20% VAT rate for the
    # platform-fee VAT so the already-approved pricing example (200 subtotal
    # -> 264 total) reproduces exactly under the new two-rate VAT model.
    op.execute(
        "UPDATE platform_settings SET "
        "vat_platform_fee_type = 'PERCENTAGE', vat_platform_fee_value = 20.00, "
        "deposit_type = 'PERCENTAGE', deposit_value = 10.00 "
        "WHERE vat_platform_fee_type IS NULL"
    )

    op.alter_column('platform_settings', 'vat_platform_fee_type', nullable=False)
    op.alter_column('platform_settings', 'vat_platform_fee_value', nullable=False)
    op.alter_column('platform_settings', 'deposit_type', nullable=False)
    op.alter_column('platform_settings', 'deposit_value', nullable=False)

    op.drop_constraint('ck_platform_settings_value_ranges', 'platform_settings', type_='check')
    op.create_check_constraint(
        'ck_platform_settings_value_ranges',
        'platform_settings',
        _NEW_CHECK_SQL,
    )


def downgrade() -> None:
    op.drop_constraint('ck_platform_settings_value_ranges', 'platform_settings', type_='check')
    op.create_check_constraint(
        'ck_platform_settings_value_ranges',
        'platform_settings',
        _OLD_CHECK_SQL,
    )
    op.drop_column('platform_settings', 'deposit_value')
    op.drop_column('platform_settings', 'deposit_type')
    op.drop_column('platform_settings', 'vat_platform_fee_value')
    op.drop_column('platform_settings', 'vat_platform_fee_type')
