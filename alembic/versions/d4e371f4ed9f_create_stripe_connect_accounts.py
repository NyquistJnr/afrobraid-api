"""create stripe connect accounts

Revision ID: d4e371f4ed9f
Revises: cce7112d0d36
Create Date: 2026-07-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e371f4ed9f'
down_revision: Union[str, None] = 'cce7112d0d36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stripe_connect_accounts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('braider_id', sa.UUID(), nullable=False),
        sa.Column('stripe_account_id', sa.String(length=64), nullable=False),
        sa.Column('charges_enabled', sa.Boolean(), nullable=False),
        sa.Column('payouts_enabled', sa.Boolean(), nullable=False),
        sa.Column('details_submitted', sa.Boolean(), nullable=False),
        sa.Column('disabled_reason', sa.String(length=255), nullable=True),
        sa.Column('requirements_currently_due', sa.Text(), nullable=True),
        sa.Column('last_webhook_payload', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['braider_id'], ['braider_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_stripe_connect_accounts_braider_id'),
        'stripe_connect_accounts',
        ['braider_id'],
        unique=True,
    )
    op.create_index(
        op.f('ix_stripe_connect_accounts_stripe_account_id'),
        'stripe_connect_accounts',
        ['stripe_account_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_stripe_connect_accounts_stripe_account_id'),
        table_name='stripe_connect_accounts',
    )
    op.drop_index(
        op.f('ix_stripe_connect_accounts_braider_id'), table_name='stripe_connect_accounts'
    )
    op.drop_table('stripe_connect_accounts')
