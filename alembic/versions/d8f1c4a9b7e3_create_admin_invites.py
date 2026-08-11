"""create admin_invites

Revision ID: d8f1c4a9b7e3
Revises: 9a1c2e7f4b6d
Create Date: 2026-08-11 00:00:00.000000

Backs the invite-only ADMIN account creation flow (see
app.modules.auth.service.invite_admin/accept_admin_invite_*) - regular
signup/social login already reject "ADMIN" as a user_type, so this is the
only path to a new ADMIN user.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd8f1c4a9b7e3'
down_revision: Union[str, None] = '9a1c2e7f4b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'admin_invites',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('invited_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index(op.f('ix_admin_invites_email'), 'admin_invites', ['email'], unique=False)
    op.create_index(op.f('ix_admin_invites_token_hash'), 'admin_invites', ['token_hash'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_admin_invites_token_hash'), table_name='admin_invites')
    op.drop_index(op.f('ix_admin_invites_email'), table_name='admin_invites')
    op.drop_table('admin_invites')
