"""add booking rescheduled notification type

Revision ID: 9a1c2e7f4b6d
Revises: bc7c5af21ea4
Create Date: 2026-08-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a1c2e7f4b6d'
down_revision: Union[str, None] = 'bc7c5af21ea4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Same reasoning as 707d295350ed_add_notification_types.py - Alembic
    # autogenerate doesn't reliably detect Postgres enum VALUE insertions.
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'BOOKING_RESCHEDULED'")


def downgrade() -> None:
    # Postgres has no ALTER TYPE ... DROP VALUE - same convention as
    # 707d295350ed_add_notification_types.py.
    pass
