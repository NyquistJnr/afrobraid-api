"""add chat and notifications

Revision ID: a4d6f1c8b3e2
Revises: 5ab86502815f
Create Date: 2026-08-08 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'a4d6f1c8b3e2'
down_revision: Union[str, None] = '5ab86502815f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _chat_message_status() -> postgresql.ENUM:
    # The type is created once via raw SQL below - create_type=False stops
    # each create_table that reuses it from also trying to CREATE TYPE
    # (see 0e6486dca8e9 for why that reliably fails when reused, and note
    # the generic sa.Enum(create_type=False) does NOT reliably suppress this
    # the way postgresql.ENUM does).
    return postgresql.ENUM('SENT', 'FLAGGED', name='chat_message_status', create_type=False)


def _chat_translation_status() -> postgresql.ENUM:
    return postgresql.ENUM(
        'NOT_APPLICABLE', 'PENDING', 'DONE', 'FAILED', name='chat_translation_status', create_type=False
    )


def _chat_report_reason() -> postgresql.ENUM:
    return postgresql.ENUM(
        'HARASSMENT', 'INAPPROPRIATE_CONTENT', 'SPAM', 'SCAM_OR_FRAUD',
        'OFF_PLATFORM_SOLICITATION', 'OTHER', name='chat_report_reason', create_type=False,
    )


def _chat_report_status() -> postgresql.ENUM:
    return postgresql.ENUM('OPEN', 'UNDER_REVIEW', 'RESOLVED', 'DISMISSED', name='chat_report_status', create_type=False)


def _notification_type() -> postgresql.ENUM:
    return postgresql.ENUM('CHAT_NEW_MESSAGE', 'CHAT_MESSAGE_FLAGGED', name='notification_type', create_type=False)


def upgrade() -> None:
    op.add_column('users', sa.Column('chat_locale', sa.String(length=5), nullable=True))

    op.execute("CREATE TYPE chat_message_status AS ENUM ('SENT', 'FLAGGED')")
    op.execute("CREATE TYPE chat_translation_status AS ENUM ('NOT_APPLICABLE', 'PENDING', 'DONE', 'FAILED')")
    op.execute(
        "CREATE TYPE chat_report_reason AS ENUM ("
        "'HARASSMENT', 'INAPPROPRIATE_CONTENT', 'SPAM', 'SCAM_OR_FRAUD', "
        "'OFF_PLATFORM_SOLICITATION', 'OTHER')"
    )
    op.execute("CREATE TYPE chat_report_status AS ENUM ('OPEN', 'UNDER_REVIEW', 'RESOLVED', 'DISMISSED')")
    op.execute("CREATE TYPE notification_type AS ENUM ('CHAT_NEW_MESSAGE', 'CHAT_MESSAGE_FLAGGED')")

    op.create_table(
        'chat_threads',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('booking_id', sa.UUID(), nullable=False),
        sa.Column('customer_id', sa.UUID(), nullable=False),
        sa.Column('braider_user_id', sa.UUID(), nullable=False),
        sa.Column('customer_last_read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('braider_last_read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_message_preview', sa.String(length=280), nullable=True),
        sa.Column('last_message_flagged', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['braider_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('booking_id'),
    )
    op.create_index(op.f('ix_chat_threads_customer_id'), 'chat_threads', ['customer_id'], unique=False)
    op.create_index(op.f('ix_chat_threads_braider_user_id'), 'chat_threads', ['braider_user_id'], unique=False)
    op.create_index(op.f('ix_chat_threads_last_message_at'), 'chat_threads', ['last_message_at'], unique=False)

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('thread_id', sa.UUID(), nullable=False),
        sa.Column('sender_id', sa.UUID(), nullable=False),
        sa.Column('status', _chat_message_status(), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('body_locale', sa.String(length=5), nullable=True),
        sa.Column('body_hash', sa.String(length=64), nullable=True),
        sa.Column('violation_types', sa.String(length=255), nullable=True),
        sa.Column('translated_body', sa.Text(), nullable=True),
        sa.Column('translated_locale', sa.String(length=5), nullable=True),
        sa.Column('translation_status', _chat_translation_status(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "(status = 'FLAGGED' AND body IS NULL AND body_hash IS NOT NULL) OR "
            "(status = 'SENT' AND body IS NOT NULL AND body_hash IS NULL)",
            name='ck_chat_messages_flagged_body',
        ),
        sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chat_messages_thread_id'), 'chat_messages', ['thread_id'], unique=False)
    op.create_index(op.f('ix_chat_messages_sender_id'), 'chat_messages', ['sender_id'], unique=False)
    op.create_index(op.f('ix_chat_messages_created_at'), 'chat_messages', ['created_at'], unique=False)

    op.create_table(
        'chat_reports',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('thread_id', sa.UUID(), nullable=False),
        sa.Column('reporter_id', sa.UUID(), nullable=False),
        sa.Column('reported_user_id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.UUID(), nullable=True),
        sa.Column('reason', _chat_report_reason(), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('status', _chat_report_status(), nullable=False),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('reporter_id != reported_user_id', name='ck_chat_reports_not_self'),
        sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reporter_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reported_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chat_reports_thread_id'), 'chat_reports', ['thread_id'], unique=False)
    op.create_index(op.f('ix_chat_reports_reporter_id'), 'chat_reports', ['reporter_id'], unique=False)
    op.create_index(op.f('ix_chat_reports_reported_user_id'), 'chat_reports', ['reported_user_id'], unique=False)

    op.create_table(
        'notifications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('type', _notification_type(), nullable=False),
        sa.Column('title_key', sa.String(length=100), nullable=False),
        sa.Column('body_key', sa.String(length=100), nullable=False),
        sa.Column('body_params', JSONB(), nullable=False),
        sa.Column('related_type', sa.String(length=50), nullable=True),
        sa.Column('related_id', sa.UUID(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_notifications_is_read'), 'notifications', ['is_read'], unique=False)
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_is_read'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')

    op.drop_index(op.f('ix_chat_reports_reported_user_id'), table_name='chat_reports')
    op.drop_index(op.f('ix_chat_reports_reporter_id'), table_name='chat_reports')
    op.drop_index(op.f('ix_chat_reports_thread_id'), table_name='chat_reports')
    op.drop_table('chat_reports')

    op.drop_index(op.f('ix_chat_messages_created_at'), table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_sender_id'), table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_thread_id'), table_name='chat_messages')
    op.drop_table('chat_messages')

    op.drop_index(op.f('ix_chat_threads_last_message_at'), table_name='chat_threads')
    op.drop_index(op.f('ix_chat_threads_braider_user_id'), table_name='chat_threads')
    op.drop_index(op.f('ix_chat_threads_customer_id'), table_name='chat_threads')
    op.drop_table('chat_threads')

    op.drop_column('users', 'chat_locale')

    op.execute("DROP TYPE notification_type")
    op.execute("DROP TYPE chat_report_status")
    op.execute("DROP TYPE chat_report_reason")
    op.execute("DROP TYPE chat_translation_status")
    op.execute("DROP TYPE chat_message_status")
