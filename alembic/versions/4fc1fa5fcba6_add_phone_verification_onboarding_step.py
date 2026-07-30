"""add phone verification onboarding step

Revision ID: 4fc1fa5fcba6
Revises: fc684c8459b8
Create Date: 2026-07-30 15:42:25.902441

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4fc1fa5fcba6'
down_revision: Union[str, None] = 'fc684c8459b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alembic autogenerate doesn't reliably detect Postgres enum VALUE
    # insertions, so this migration is hand-written. ALTER TYPE ... ADD VALUE
    # can run inside a transaction on Postgres 12+ as long as the new value
    # isn't used within that same transaction (it isn't, here) - confirmed
    # against Postgres 18 in this environment.
    op.execute(
        "ALTER TYPE onboarding_step ADD VALUE IF NOT EXISTS 'PHONE_VERIFICATION' "
        "AFTER 'BUSINESS_INFO'"
    )
    op.add_column(
        "braider_onboarding_statuses",
        sa.Column("phone_verification_completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("braider_onboarding_statuses", "phone_verification_completed_at")
    # Postgres has no ALTER TYPE ... DROP VALUE - cleanly removing an enum
    # value requires rebuilding the whole type (rename it, create a new type
    # without the value, migrate every column via a CASE mapping, drop the
    # old type). Not done here: 'PHONE_VERIFICATION' remains a valid (just
    # unused) enum value after downgrade rather than over-engineering a
    # rarely-exercised rollback path.
