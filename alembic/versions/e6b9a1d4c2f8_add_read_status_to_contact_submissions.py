"""add read status to contact submissions

Revision ID: e6b9a1d4c2f8
Revises: d8f1c4a9b7e3
Create Date: 2026-08-12 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6b9a1d4c2f8"
down_revision: str | None = "d8f1c4a9b7e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contact_submissions",
        sa.Column("is_read", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "contact_submissions",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "contact_submissions",
        sa.Column("read_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_contact_submissions_is_read"),
        "contact_submissions",
        ["is_read"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_contact_submissions_read_by_admin_id_users"),
        "contact_submissions",
        "users",
        ["read_by_admin_id"],
        ["id"],
    )
    op.alter_column("contact_submissions", "is_read", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_contact_submissions_read_by_admin_id_users"),
        "contact_submissions",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_contact_submissions_is_read"), table_name="contact_submissions")
    op.drop_column("contact_submissions", "read_by_admin_id")
    op.drop_column("contact_submissions", "read_at")
    op.drop_column("contact_submissions", "is_read")
