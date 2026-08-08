import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders.models import BraiderOnboardingStatus, BraiderProfile
from app.modules.users.models import User


async def get_profile_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> BraiderProfile | None:
    result = await db.execute(select(BraiderProfile).where(BraiderProfile.user_id == user_id))
    return result.scalar_one_or_none()


async def get_profile_by_id(db: AsyncSession, profile_id: uuid.UUID) -> BraiderProfile | None:
    return await db.get(BraiderProfile, profile_id)


async def list_display_names(
    db: AsyncSession, braider_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Batched braider display-name lookup: business_name if set, else the
    owning user's full name - same fallback used for the Stripe customer
    name in bookings/service.py, so a braider without a business_name still
    shows up as something in a customer's booking list."""
    if not braider_ids:
        return {}
    result = await db.execute(
        select(BraiderProfile.id, BraiderProfile.business_name, User.first_name, User.last_name)
        .join(User, User.id == BraiderProfile.user_id)
        .where(BraiderProfile.id.in_(braider_ids))
    )
    return {
        row.id: row.business_name or f"{row.first_name} {row.last_name or ''}".strip()
        for row in result.all()
    }


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
