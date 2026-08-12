"""add tryon failure reason

Revision ID: aa4f0e29c18b
Revises: e6b9a1d4c2f8
Create Date: 2026-08-12 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aa4f0e29c18b"
down_revision: str | None = "e6b9a1d4c2f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

tryon_failure_reason = sa.Enum(
    "GENERATION_FAILED",
    "AI_CREDIT_EXHAUSTED",
    name="tryon_failure_reason",
)


def upgrade() -> None:
    tryon_failure_reason.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "hairstyle_tryons",
        sa.Column("failure_reason", tryon_failure_reason, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("hairstyle_tryons", "failure_reason")
    tryon_failure_reason.drop(op.get_bind(), checkfirst=True)
