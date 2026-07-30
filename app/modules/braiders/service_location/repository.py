import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders.service_location.models import BraiderServiceLocation


async def get_by_braider_id(
    db: AsyncSession, braider_id: uuid.UUID
) -> BraiderServiceLocation | None:
    result = await db.execute(
        select(BraiderServiceLocation).where(BraiderServiceLocation.braider_id == braider_id)
    )
    return result.scalar_one_or_none()


async def create_for_braider(db: AsyncSession, braider_id: uuid.UUID) -> BraiderServiceLocation:
    location = BraiderServiceLocation(braider_id=braider_id)
    db.add(location)
    await db.flush()
    return location
