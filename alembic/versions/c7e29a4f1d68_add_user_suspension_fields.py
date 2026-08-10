"""add user suspension fields

Revision ID: c7e29a4f1d68
Revises: b3f4d8a12e56
Create Date: 2026-08-24 00:10:00.000000

`is_active` already gates login end-to-end (see app.modules.auth) but had
no way to record *why* a user was deactivated. These two nullable columns
back the new admin suspend/unsuspend endpoints - both null means "never
suspended" (or "unsuspended"), not just "reason not given".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e29a4f1d68'
down_revision: Union[str, None] = 'b3f4d8a12e56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('suspension_reason', sa.String(length=500), nullable=True))
    op.add_column('users', sa.Column('suspended_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'suspended_at')
    op.drop_column('users', 'suspension_reason')
