"""create hairstyle tryons

Revision ID: 5ab86502815f
Revises: 1b7e118b0927
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum


# revision identifiers, used by Alembic.
revision: str = '5ab86502815f'
down_revision: Union[str, None] = '1b7e118b0927'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tryon_status_column() -> PGEnum:
    # See 0e6486dca8e9 (translation_source) - the type is created once via
    # raw SQL below; create_type=False here stops create_table from also
    # trying to create it (and colliding with the one we just made).
    return PGEnum('PROCESSING', 'COMPLETED', 'FAILED', name='tryon_status', create_type=False)


def upgrade() -> None:
    op.execute("CREATE TYPE tryon_status AS ENUM ('PROCESSING', 'COMPLETED', 'FAILED')")

    op.create_table(
        'hairstyle_tryons',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('style_id', sa.UUID(), nullable=True),
        sa.Column('style_variation_id', sa.UUID(), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('source_object_key', sa.String(length=500), nullable=True),
        sa.Column('result_object_key', sa.String(length=500), nullable=True),
        sa.Column('status', _tryon_status_column(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['style_id'], ['styles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['style_variation_id'], ['style_variations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_hairstyle_tryons_user_id'), 'hairstyle_tryons', ['user_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_hairstyle_tryons_user_id'), table_name='hairstyle_tryons')
    op.drop_table('hairstyle_tryons')
    op.execute("DROP TYPE tryon_status")
