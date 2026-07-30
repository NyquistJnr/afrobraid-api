import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders.offerings.models import (
    BraiderStyle,
    BraiderStyleAddon,
    BraiderStyleVariation,
)


async def get_braider_style_by_style_id(
    db: AsyncSession, braider_id: uuid.UUID, style_id: uuid.UUID
) -> BraiderStyle | None:
    result = await db.execute(
        select(BraiderStyle).where(
            BraiderStyle.braider_id == braider_id, BraiderStyle.style_id == style_id
        )
    )
    return result.scalar_one_or_none()


async def get_braider_style_by_id(
    db: AsyncSession, braider_style_id: uuid.UUID
) -> BraiderStyle | None:
    return await db.get(BraiderStyle, braider_style_id)


async def list_braider_styles(db: AsyncSession, braider_id: uuid.UUID) -> list[BraiderStyle]:
    result = await db.execute(
        select(BraiderStyle)
        .where(BraiderStyle.braider_id == braider_id)
        .order_by(BraiderStyle.created_at)
    )
    return list(result.scalars().all())


async def create_braider_style(
    db: AsyncSession,
    *,
    braider_id: uuid.UUID,
    style_id: uuid.UUID,
    base_price: Decimal,
    duration_minutes: int | None,
) -> BraiderStyle:
    braider_style = BraiderStyle(
        braider_id=braider_id,
        style_id=style_id,
        base_price=base_price,
        duration_minutes=duration_minutes,
    )
    db.add(braider_style)
    await db.flush()
    return braider_style


async def delete_braider_style(db: AsyncSession, braider_style: BraiderStyle) -> None:
    await db.delete(braider_style)
    await db.flush()


async def list_braider_style_variations(
    db: AsyncSession, braider_style_id: uuid.UUID
) -> list[BraiderStyleVariation]:
    result = await db.execute(
        select(BraiderStyleVariation).where(
            BraiderStyleVariation.braider_style_id == braider_style_id
        )
    )
    return list(result.scalars().all())


async def create_braider_style_variation(
    db: AsyncSession,
    *,
    braider_style_id: uuid.UUID,
    style_variation_id: uuid.UUID,
    price: Decimal,
) -> BraiderStyleVariation:
    row = BraiderStyleVariation(
        braider_style_id=braider_style_id, style_variation_id=style_variation_id, price=price
    )
    db.add(row)
    await db.flush()
    return row


async def delete_braider_style_variations(db: AsyncSession, braider_style_id: uuid.UUID) -> None:
    for row in await list_braider_style_variations(db, braider_style_id):
        await db.delete(row)
    await db.flush()


async def list_braider_style_addons(
    db: AsyncSession, braider_style_id: uuid.UUID
) -> list[BraiderStyleAddon]:
    result = await db.execute(
        select(BraiderStyleAddon).where(BraiderStyleAddon.braider_style_id == braider_style_id)
    )
    return list(result.scalars().all())


async def create_braider_style_addon(
    db: AsyncSession,
    *,
    braider_style_id: uuid.UUID,
    addon_id: uuid.UUID,
    price: Decimal,
    is_required: bool,
) -> BraiderStyleAddon:
    row = BraiderStyleAddon(
        braider_style_id=braider_style_id, addon_id=addon_id, price=price, is_required=is_required
    )
    db.add(row)
    await db.flush()
    return row


async def delete_braider_style_addons(db: AsyncSession, braider_style_id: uuid.UUID) -> None:
    for row in await list_braider_style_addons(db, braider_style_id):
        await db.delete(row)
    await db.flush()
