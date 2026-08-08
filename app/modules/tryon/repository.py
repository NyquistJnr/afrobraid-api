import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tryon.models import HairstyleTryOn, TryOnStatus


async def get_tryon_by_id(db: AsyncSession, tryon_id: uuid.UUID) -> HairstyleTryOn | None:
    return await db.get(HairstyleTryOn, tryon_id)


async def list_tryons_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[HairstyleTryOn]:
    result = await db.execute(
        select(HairstyleTryOn)
        .where(HairstyleTryOn.user_id == user_id)
        .order_by(HairstyleTryOn.created_at.desc())
    )
    return list(result.scalars().all())


async def count_pending_for_user(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(HairstyleTryOn)
        .where(
            HairstyleTryOn.user_id == user_id, HairstyleTryOn.status == TryOnStatus.PROCESSING
        )
    )
    return result.scalar_one()


async def create_tryon(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    style_id: uuid.UUID | None,
    style_variation_id: uuid.UUID | None,
    description: str | None,
    prompt: str,
    source_object_key: str,
) -> HairstyleTryOn:
    tryon = HairstyleTryOn(
        user_id=user_id,
        style_id=style_id,
        style_variation_id=style_variation_id,
        description=description,
        prompt=prompt,
        source_object_key=source_object_key,
        status=TryOnStatus.PROCESSING,
    )
    db.add(tryon)
    await db.flush()
    return tryon


async def delete_tryon(db: AsyncSession, tryon: HairstyleTryOn) -> None:
    await db.delete(tryon)
    await db.flush()
