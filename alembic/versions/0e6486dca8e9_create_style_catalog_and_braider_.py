"""create style catalog and braider offerings

Revision ID: 0e6486dca8e9
Revises: 4fc1fa5fcba6
Create Date: 2026-07-30 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum


# revision identifiers, used by Alembic.
revision: str = '0e6486dca8e9'
down_revision: Union[str, None] = '4fc1fa5fcba6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _translation_source_column() -> PGEnum:
    # `translation_source` is shared by ~15 columns across 4 of the tables
    # below. Generic sa.Enum's create_type=False doesn't reliably suppress
    # re-creation across that many reuses in one migration (confirmed via a
    # standalone repro - it still raises DuplicateObjectError on the second
    # table); using the PG-specific ENUM type with create_type=False does.
    # The type itself is created once via raw SQL below instead of relying
    # on SQLAlchemy's own (also unreliable here) checkfirst-based .create().
    return PGEnum(
        'HUMAN', 'MACHINE', 'PENDING', 'FAILED', name='translation_source', create_type=False
    )


def upgrade() -> None:
    op.execute("CREATE TYPE translation_source AS ENUM ('HUMAN', 'MACHINE', 'PENDING', 'FAILED')")

    op.create_table(
        'style_categories',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('slug', sa.String(length=150), nullable=False),
        sa.Column('name_en', sa.String(length=150), nullable=False),
        sa.Column('name_de', sa.String(length=150), nullable=True),
        sa.Column('name_fr', sa.String(length=150), nullable=True),
        sa.Column('name_en_source', _translation_source_column(), nullable=True),
        sa.Column('name_de_source', _translation_source_column(), nullable=True),
        sa.Column('name_fr_source', _translation_source_column(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_style_categories_slug'), 'style_categories', ['slug'], unique=True)

    op.create_table(
        'styles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=True),
        sa.Column('slug', sa.String(length=150), nullable=False),
        sa.Column('name_en', sa.String(length=150), nullable=False),
        sa.Column('name_de', sa.String(length=150), nullable=True),
        sa.Column('name_fr', sa.String(length=150), nullable=True),
        sa.Column('name_en_source', _translation_source_column(), nullable=True),
        sa.Column('name_de_source', _translation_source_column(), nullable=True),
        sa.Column('name_fr_source', _translation_source_column(), nullable=True),
        sa.Column('description_en', sa.Text(), nullable=True),
        sa.Column('description_de', sa.Text(), nullable=True),
        sa.Column('description_fr', sa.Text(), nullable=True),
        sa.Column('description_en_source', _translation_source_column(), nullable=True),
        sa.Column('description_de_source', _translation_source_column(), nullable=True),
        sa.Column('description_fr_source', _translation_source_column(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['style_categories.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_styles_category_id'), 'styles', ['category_id'], unique=False)
    op.create_index(op.f('ix_styles_slug'), 'styles', ['slug'], unique=True)

    op.create_table(
        'style_images',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('style_id', sa.UUID(), nullable=False),
        sa.Column('object_key', sa.String(length=500), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['style_id'], ['styles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('style_id', 'position', name='uq_style_image_position'),
    )
    op.create_index(op.f('ix_style_images_style_id'), 'style_images', ['style_id'], unique=False)

    op.create_table(
        'style_variations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('style_id', sa.UUID(), nullable=False),
        sa.Column('name_en', sa.String(length=150), nullable=False),
        sa.Column('name_de', sa.String(length=150), nullable=True),
        sa.Column('name_fr', sa.String(length=150), nullable=True),
        sa.Column('name_en_source', _translation_source_column(), nullable=True),
        sa.Column('name_de_source', _translation_source_column(), nullable=True),
        sa.Column('name_fr_source', _translation_source_column(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['style_id'], ['styles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_style_variations_style_id'), 'style_variations', ['style_id'], unique=False)

    op.create_table(
        'addons',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('slug', sa.String(length=150), nullable=False),
        sa.Column('name_en', sa.String(length=150), nullable=False),
        sa.Column('name_de', sa.String(length=150), nullable=True),
        sa.Column('name_fr', sa.String(length=150), nullable=True),
        sa.Column('name_en_source', _translation_source_column(), nullable=True),
        sa.Column('name_de_source', _translation_source_column(), nullable=True),
        sa.Column('name_fr_source', _translation_source_column(), nullable=True),
        sa.Column('suggested_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_addons_slug'), 'addons', ['slug'], unique=True)

    op.create_table(
        'braider_styles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('braider_id', sa.UUID(), nullable=False),
        sa.Column('style_id', sa.UUID(), nullable=False),
        sa.Column('base_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['braider_id'], ['braider_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['style_id'], ['styles.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('braider_id', 'style_id', name='uq_braider_style'),
    )
    op.create_index(op.f('ix_braider_styles_braider_id'), 'braider_styles', ['braider_id'], unique=False)
    op.create_index(op.f('ix_braider_styles_style_id'), 'braider_styles', ['style_id'], unique=False)

    op.create_table(
        'braider_style_variations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('braider_style_id', sa.UUID(), nullable=False),
        sa.Column('style_variation_id', sa.UUID(), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['braider_style_id'], ['braider_styles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['style_variation_id'], ['style_variations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('braider_style_id', 'style_variation_id', name='uq_braider_style_variation'),
    )
    op.create_index(
        op.f('ix_braider_style_variations_braider_style_id'),
        'braider_style_variations',
        ['braider_style_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_braider_style_variations_style_variation_id'),
        'braider_style_variations',
        ['style_variation_id'],
        unique=False,
    )

    op.create_table(
        'braider_style_addons',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('braider_style_id', sa.UUID(), nullable=False),
        sa.Column('addon_id', sa.UUID(), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['addon_id'], ['addons.id']),
        sa.ForeignKeyConstraint(['braider_style_id'], ['braider_styles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('braider_style_id', 'addon_id', name='uq_braider_style_addon'),
    )
    op.create_index(
        op.f('ix_braider_style_addons_addon_id'), 'braider_style_addons', ['addon_id'], unique=False
    )
    op.create_index(
        op.f('ix_braider_style_addons_braider_style_id'),
        'braider_style_addons',
        ['braider_style_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_braider_style_addons_braider_style_id'), table_name='braider_style_addons')
    op.drop_index(op.f('ix_braider_style_addons_addon_id'), table_name='braider_style_addons')
    op.drop_table('braider_style_addons')

    op.drop_index(
        op.f('ix_braider_style_variations_style_variation_id'), table_name='braider_style_variations'
    )
    op.drop_index(
        op.f('ix_braider_style_variations_braider_style_id'), table_name='braider_style_variations'
    )
    op.drop_table('braider_style_variations')

    op.drop_index(op.f('ix_braider_styles_style_id'), table_name='braider_styles')
    op.drop_index(op.f('ix_braider_styles_braider_id'), table_name='braider_styles')
    op.drop_table('braider_styles')

    op.drop_index(op.f('ix_addons_slug'), table_name='addons')
    op.drop_table('addons')

    op.drop_index(op.f('ix_style_variations_style_id'), table_name='style_variations')
    op.drop_table('style_variations')

    op.drop_index(op.f('ix_style_images_style_id'), table_name='style_images')
    op.drop_table('style_images')

    op.drop_index(op.f('ix_styles_slug'), table_name='styles')
    op.drop_index(op.f('ix_styles_category_id'), table_name='styles')
    op.drop_table('styles')

    op.drop_index(op.f('ix_style_categories_slug'), table_name='style_categories')
    op.drop_table('style_categories')

    # Shared by all the tables above - see the comment in upgrade().
    op.execute("DROP TYPE IF EXISTS translation_source")
