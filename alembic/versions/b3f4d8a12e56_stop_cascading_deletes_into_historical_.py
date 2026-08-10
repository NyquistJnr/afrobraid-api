"""stop cascading deletes into historical/financial/moderation records

Revision ID: b3f4d8a12e56
Revises: a1c72e9f0b3d
Create Date: 2026-08-24 00:00:00.000000

Follow-up to a1c72e9f0b3d (which fixed bookings.braider_style_id). An audit
of every ON DELETE CASCADE in the schema found several more FKs where
deleting a "manageable" parent record (a user account, a braider profile,
a booking) would silently cascade-delete something valuable that should
outlive it:

  - bookings.customer_id / bookings.braider_id -> users / braider_profiles:
    a booking is a financial record; deleting a user or braider profile
    would take every booking, and transitively booking_items/booking_payments
    (real Stripe payment records), with it.
  - reviews.customer_id / reviews.braider_id -> users / braider_profiles:
    reviews are customer-authored, moderated, historical content.
  - chat_threads.booking_id / customer_id / braider_user_id, and
    chat_messages.sender_id, chat_reports.reporter_id / reported_user_id ->
    bookings / users: ChatThread's own docstring says a thread must survive
    a booking's cancellation "so a dispute can still be discussed" - cascading
    it off the booking or either participant undermines that, and would
    delete open abuse reports along with the accused's account.

None of these are exploitable today (no delete-user/delete-booking/
delete-review endpoint exists yet), but the FKs already permit a future
account-deletion or cleanup feature to silently destroy this data. This
migration drops each CASCADE and recreates the same FK with no ON DELETE
action (Postgres default NO ACTION / RESTRICT-equivalent), so any future
delete is refused instead of silently cascading, matching the fix already
applied to bookings.braider_style_id.

Sub-record FKs that are NOT touched here because they're appropriate
(genuinely owned children with no independent value): booking_items /
booking_payments -> bookings, chat_messages.thread_id / chat_reports.thread_id
-> chat_threads, auth/onboarding/veriff -> users, braider_styles and their
own variations/addons -> braider_profiles / braider_styles, notifications ->
users, booking_calculation_addons -> booking_calculations.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3f4d8a12e56'
down_revision: Union[str, None] = 'a1c72e9f0b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (constraint_name, table, referenced_table, local_column)
_FK_TO_FIX = [
    ('bookings_customer_id_fkey', 'bookings', 'users', 'customer_id'),
    ('bookings_braider_id_fkey', 'bookings', 'braider_profiles', 'braider_id'),
    ('reviews_customer_id_fkey', 'reviews', 'users', 'customer_id'),
    ('reviews_braider_id_fkey', 'reviews', 'braider_profiles', 'braider_id'),
    ('chat_threads_booking_id_fkey', 'chat_threads', 'bookings', 'booking_id'),
    ('chat_threads_customer_id_fkey', 'chat_threads', 'users', 'customer_id'),
    ('chat_threads_braider_user_id_fkey', 'chat_threads', 'users', 'braider_user_id'),
    ('chat_messages_sender_id_fkey', 'chat_messages', 'users', 'sender_id'),
    ('chat_reports_reporter_id_fkey', 'chat_reports', 'users', 'reporter_id'),
    ('chat_reports_reported_user_id_fkey', 'chat_reports', 'users', 'reported_user_id'),
]


def upgrade() -> None:
    for constraint_name, table, ref_table, column in _FK_TO_FIX:
        op.drop_constraint(constraint_name, table, type_='foreignkey')
        op.create_foreign_key(constraint_name, table, ref_table, [column], ['id'])


def downgrade() -> None:
    for constraint_name, table, ref_table, column in _FK_TO_FIX:
        op.drop_constraint(constraint_name, table, type_='foreignkey')
        op.create_foreign_key(
            constraint_name, table, ref_table, [column], ['id'], ondelete='CASCADE'
        )
