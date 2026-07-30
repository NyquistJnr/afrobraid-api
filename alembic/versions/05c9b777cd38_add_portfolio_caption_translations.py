"""add portfolio caption translations

Revision ID: 05c9b777cd38
Revises: 04eb5c55a370
Create Date: 2026-07-30 19:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '05c9b777cd38'
down_revision: Union[str, None] = '04eb5c55a370'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('portfolio_images', 'caption')

    # `bio_source` already exists (created for braider_profiles.bio_*_source
    # in e2c526692fbc) - create_type=False so this doesn't try to CREATE TYPE
    # again (see 0e6486dca8e9 for why that reliably fails when reused).
    bio_source_enum = postgresql.ENUM(
        'HUMAN', 'MACHINE', 'PENDING', 'FAILED', name='bio_source', create_type=False
    )
    op.add_column('portfolio_images', sa.Column('caption_en', sa.String(length=300), nullable=True))
    op.add_column('portfolio_images', sa.Column('caption_de', sa.String(length=300), nullable=True))
    op.add_column('portfolio_images', sa.Column('caption_fr', sa.String(length=300), nullable=True))
    op.add_column('portfolio_images', sa.Column('caption_en_source', bio_source_enum, nullable=True))
    op.add_column('portfolio_images', sa.Column('caption_de_source', bio_source_enum, nullable=True))
    op.add_column('portfolio_images', sa.Column('caption_fr_source', bio_source_enum, nullable=True))


def downgrade() -> None:
    op.drop_column('portfolio_images', 'caption_fr_source')
    op.drop_column('portfolio_images', 'caption_de_source')
    op.drop_column('portfolio_images', 'caption_en_source')
    op.drop_column('portfolio_images', 'caption_fr')
    op.drop_column('portfolio_images', 'caption_de')
    op.drop_column('portfolio_images', 'caption_en')
    op.add_column('portfolio_images', sa.Column('caption', sa.String(length=300), nullable=True))
