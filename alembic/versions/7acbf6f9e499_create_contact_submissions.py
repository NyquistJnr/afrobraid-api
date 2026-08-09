"""create contact submissions

Revision ID: 7acbf6f9e499
Revises: a4d6f1c8b3e2
Create Date: 2026-08-09 23:53:24.501317

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7acbf6f9e499'
down_revision: Union[str, None] = 'a4d6f1c8b3e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('contact_submissions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('first_name', sa.String(length=100), nullable=False),
    sa.Column('last_name', sa.String(length=100), nullable=False),
    sa.Column('phone_number', sa.String(length=20), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=True),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('platform', sa.Enum('CUSTOMER', 'BRAIDER', name='contact_platform'), nullable=False),
    sa.Column('purpose', sa.Enum('GENERAL', 'PARTNER', 'PRICING', 'FAQS', name='contact_purpose'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contact_submissions_email'), 'contact_submissions', ['email'], unique=False)
    op.create_index(op.f('ix_contact_submissions_platform'), 'contact_submissions', ['platform'], unique=False)
    op.create_index(op.f('ix_contact_submissions_purpose'), 'contact_submissions', ['purpose'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_contact_submissions_purpose'), table_name='contact_submissions')
    op.drop_index(op.f('ix_contact_submissions_platform'), table_name='contact_submissions')
    op.drop_index(op.f('ix_contact_submissions_email'), table_name='contact_submissions')
    op.drop_table('contact_submissions')
    sa.Enum(name='contact_purpose').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='contact_platform').drop(op.get_bind(), checkfirst=True)
