import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders.portfolio.models import PortfolioImage


async def list_images(db: AsyncSession, braider_id: uuid.UUID) -> list[PortfolioImage]:
    result = await db.execute(
        select(PortfolioImage)
        .where(PortfolioImage.braider_id == braider_id)
        .order_by(PortfolioImage.position)
    )
    return list(result.scalars().all())


async def get_image_by_id(db: AsyncSession, image_id: uuid.UUID) -> PortfolioImage | None:
    return await db.get(PortfolioImage, image_id)


async def create_image(
    db: AsyncSession,
    *,
    braider_id: uuid.UUID,
    object_key: str,
    caption: str | None,
    position: int,
) -> PortfolioImage:
    image = PortfolioImage(
        braider_id=braider_id, object_key=object_key, caption=caption, position=position
    )
    db.add(image)
    await db.flush()
    return image


async def delete_image(db: AsyncSession, image: PortfolioImage) -> None:
    await db.delete(image)
    await db.flush()
