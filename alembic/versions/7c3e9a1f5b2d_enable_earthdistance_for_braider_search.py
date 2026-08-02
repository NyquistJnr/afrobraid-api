"""enable earthdistance for braider search

Revision ID: 7c3e9a1f5b2d
Revises: d4e371f4ed9f
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '7c3e9a1f5b2d'
down_revision: Union[str, None] = 'd4e371f4ed9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS cube")
    op.execute("CREATE EXTENSION IF NOT EXISTS earthdistance")
    op.execute(
        "CREATE INDEX ix_braider_service_locations_earth "
        "ON braider_service_locations "
        "USING gist (ll_to_earth(latitude, longitude)) "
        "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_braider_service_locations_earth")
    op.execute("DROP EXTENSION IF EXISTS earthdistance")
    op.execute("DROP EXTENSION IF EXISTS cube")
