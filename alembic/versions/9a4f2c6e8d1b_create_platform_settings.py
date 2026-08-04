"""create platform settings

Revision ID: 9a4f2c6e8d1b
Revises: 7c3e9a1f5b2d
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum


# revision identifiers, used by Alembic.
revision: str = '9a4f2c6e8d1b'
down_revision: Union[str, None] = '7c3e9a1f5b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _setting_value_type_column() -> PGEnum:
    # Shared by two columns below - see 0e6486dca8e9 for why the type is
    # created once via raw SQL and every column reference uses
    # create_type=False instead of relying on sa.Enum's own checkfirst.
    return PGEnum('PERCENTAGE', 'FIXED', name='setting_value_type', create_type=False)


def upgrade() -> None:
    op.execute("CREATE TYPE setting_value_type AS ENUM ('PERCENTAGE', 'FIXED')")

    op.create_table(
        'platform_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('platform_fee_type', _setting_value_type_column(), nullable=False),
        sa.Column('platform_fee_value', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('vat_type', _setting_value_type_column(), nullable=False),
        sa.Column('vat_value', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "platform_fee_value >= 0 AND vat_value >= 0 AND "
            "(platform_fee_type != 'PERCENTAGE' OR platform_fee_value <= 100) AND "
            "(vat_type != 'PERCENTAGE' OR vat_value <= 100)",
            name='ck_platform_settings_value_ranges',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    # No seed INSERT here - app.modules.platform_settings.service lazily
    # creates the single default row (10% platform fee, 20% VAT) on first
    # GET/PATCH, same as BraiderAvailabilitySettings does per-braider.


def downgrade() -> None:
    op.drop_table('platform_settings')
    # Autogenerate doesn't drop the Postgres enum type, which would break a
    # subsequent upgrade (CREATE TYPE collides with the leftover type).
    sa.Enum(name='setting_value_type').drop(op.get_bind(), checkfirst=True)
