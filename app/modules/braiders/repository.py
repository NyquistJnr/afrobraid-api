import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders.models import BraiderOnboardingStatus, BraiderProfile


async def get_profile_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> BraiderProfile | None:
    result = await db.execute(select(BraiderProfile).where(BraiderProfile.user_id == user_id))
    return result.scalar_one_or_none()


async def get_profile_by_id(db: AsyncSession, profile_id: uuid.UUID) -> BraiderProfile | None:
    return await db.get(BraiderProfile, profile_id)


async def create_profile_for_user(db: AsyncSession, user_id: uuid.UUID) -> BraiderProfile:
    profile = BraiderProfile(user_id=user_id)
    db.add(profile)
    await db.flush()
    return profile


async def get_onboarding_status_by_user_id(
    db: AsyncSession, user_id: uuid.UUID
) -> BraiderOnboardingStatus | None:
    result = await db.execute(
        select(BraiderOnboardingStatus).where(BraiderOnboardingStatus.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_onboarding_status_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> BraiderOnboardingStatus:
    status = BraiderOnboardingStatus(user_id=user_id)
    db.add(status)
    await db.flush()
    return status
