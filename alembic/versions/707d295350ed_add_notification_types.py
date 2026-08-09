"""add notification types

Revision ID: 707d295350ed
Revises: 7acbf6f9e499
Create Date: 2026-08-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '707d295350ed'
down_revision: Union[str, None] = '7acbf6f9e499'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alembic autogenerate doesn't reliably detect Postgres enum VALUE
    # insertions, so this migration is hand-written (mirrors
    # 4fc1fa5fcba6_add_phone_verification_onboarding_step). Each ADD VALUE
    # runs in its own statement - Postgres doesn't allow adding more than one
    # value per ALTER TYPE call.
    for value in (
        "PAYMENT_DEPOSIT_SUCCEEDED",
        "PAYMENT_FULL_SUCCEEDED",
        "PAYMENT_BALANCE_SUCCEEDED",
        "PROFILE_UPDATED",
        "PASSWORD_CHANGED",
        "NEW_LOGIN",
    ):
        op.execute(f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # Postgres has no ALTER TYPE ... DROP VALUE - cleanly removing an enum
    # value requires rebuilding the whole type. Not done here: the new values
    # remain valid (just unused) enum members after downgrade rather than
    # over-engineering a rarely-exercised rollback path.
    pass
