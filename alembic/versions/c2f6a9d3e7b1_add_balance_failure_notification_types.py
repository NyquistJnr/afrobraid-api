"""add balance failure notification types

Revision ID: c2f6a9d3e7b1
Revises: aa4f0e29c18b
Create Date: 2026-08-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2f6a9d3e7b1'
down_revision: Union[str, None] = 'aa4f0e29c18b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Same reasoning as 707d295350ed_add_notification_types.py - Alembic
    # autogenerate doesn't reliably detect Postgres enum VALUE insertions.
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'PAYMENT_BALANCE_FAILED'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'BOOKING_CANCELLED_NO_PAYMENT'")


def downgrade() -> None:
    # Postgres has no ALTER TYPE ... DROP VALUE - same convention as
    # 707d295350ed_add_notification_types.py.
    pass
