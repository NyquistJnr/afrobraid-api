"""add booking cancellation notification types

Revision ID: e7c1a4f8b0d3
Revises: d4b8e2a6f915
Create Date: 2026-08-14 00:00:00.000001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7c1a4f8b0d3'
down_revision: Union[str, None] = 'd4b8e2a6f915'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Same reasoning as 707d295350ed_add_notification_types.py - Alembic
    # autogenerate doesn't reliably detect Postgres enum VALUE insertions.
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'BOOKING_CANCELLED_BY_CUSTOMER'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'BOOKING_CANCELLED_BY_BRAIDER'")


def downgrade() -> None:
    # Postgres has no ALTER TYPE ... DROP VALUE - same convention as
    # 707d295350ed_add_notification_types.py.
    pass
