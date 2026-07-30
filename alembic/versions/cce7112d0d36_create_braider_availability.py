"""create braider availability

Revision ID: cce7112d0d36
Revises: 52664d03b80a
Create Date: 2026-07-30 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cce7112d0d36'
down_revision: Union[str, None] = '52664d03b80a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'braider_availability_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('braider_id', sa.UUID(), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False),
        sa.Column('min_notice_hours', sa.Integer(), nullable=False),
        sa.Column('max_advance_days', sa.Integer(), nullable=False),
        sa.Column('buffer_minutes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['braider_id'], ['braider_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_braider_availability_settings_braider_id'),
        'braider_availability_settings',
        ['braider_id'],
        unique=True,
    )

    op.create_table(
        'braider_weekly_availability',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('braider_id', sa.UUID(), nullable=False),
        sa.Column(
            'day_of_week',
            sa.Enum(
                'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY',
                name='day_of_week',
            ),
            nullable=False,
        ),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('end_time > start_time', name='ck_weekly_availability_end_after_start'),
        sa.ForeignKeyConstraint(['braider_id'], ['braider_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_braider_weekly_availability_braider_id'),
        'braider_weekly_availability',
        ['braider_id'],
    )

    op.create_table(
        'braider_availability_exceptions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('braider_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column(
            'exception_type',
            sa.Enum('CLOSED', 'CUSTOM_HOURS', name='availability_exception_type'),
            nullable=False,
        ),
        sa.Column('start_time', sa.Time(), nullable=True),
        sa.Column('end_time', sa.Time(), nullable=True),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "(exception_type = 'CLOSED' AND start_time IS NULL AND end_time IS NULL) OR "
            "(exception_type = 'CUSTOM_HOURS' AND start_time IS NOT NULL "
            "AND end_time IS NOT NULL AND end_time > start_time)",
            name='ck_availability_exception_times_match_type',
        ),
        sa.ForeignKeyConstraint(['braider_id'], ['braider_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_braider_availability_exceptions_braider_id'),
        'braider_availability_exceptions',
        ['braider_id'],
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_braider_availability_exceptions_braider_id'),
        table_name='braider_availability_exceptions',
    )
    op.drop_table('braider_availability_exceptions')
    sa.Enum(name='availability_exception_type').drop(op.get_bind(), checkfirst=True)

    op.drop_index(
        op.f('ix_braider_weekly_availability_braider_id'),
        table_name='braider_weekly_availability',
    )
    op.drop_table('braider_weekly_availability')
    sa.Enum(name='day_of_week').drop(op.get_bind(), checkfirst=True)

    op.drop_index(
        op.f('ix_braider_availability_settings_braider_id'),
        table_name='braider_availability_settings',
    )
    op.drop_table('braider_availability_settings')
