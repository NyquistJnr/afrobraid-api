"""stop braider_styles delete from cascading into bookings

Revision ID: a1c72e9f0b3d
Revises: 707d295350ed
Create Date: 2026-08-17 00:00:00.000000

`bookings.braider_style_id` was created with `ON DELETE CASCADE` against
`braider_styles.id` (8d4a1f2e6c93). That means a braider deleting one menu
entry (DELETE /api/v1/braiders/onboarding/services/{braider_style_id})
silently deleted every booking that ever used it - and, via their own
CASCADE, every booking_items and booking_payments row too, including
already-charged deposits/full payments. This drops that cascade so the
delete is refused (FK violation -> EntityInUseError, see
braiders/offerings/service.py) whenever bookings still reference the style,
matching how style_id/style_variation_id already behave on this same table.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c72e9f0b3d'
down_revision: Union[str, None] = '707d295350ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('bookings_braider_style_id_fkey', 'bookings', type_='foreignkey')
    op.create_foreign_key(
        'bookings_braider_style_id_fkey',
        'bookings',
        'braider_styles',
        ['braider_style_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('bookings_braider_style_id_fkey', 'bookings', type_='foreignkey')
    op.create_foreign_key(
        'bookings_braider_style_id_fkey',
        'bookings',
        'braider_styles',
        ['braider_style_id'],
        ['id'],
        ondelete='CASCADE',
    )
