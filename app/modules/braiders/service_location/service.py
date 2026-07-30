import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders import repository as braiders_repo
from app.modules.braiders.completion import (
    is_service_location_complete,
    recompute_service_location_completion,
)
from app.modules.braiders.models import BraiderOnboardingStatus, BraiderProfile
from app.modules.braiders.service_location import repository as location_repo
from app.modules.braiders.service_location.models import BraiderServiceLocation, LocationType
from app.modules.braiders.service_location.schemas import (
    ServiceLocationResponse,
    ServiceLocationUpdateRequest,
)


async def _get_or_create_profile(db: AsyncSession, user_id: uuid.UUID) -> BraiderProfile:
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    if profile is None:
        profile = await braiders_repo.create_profile_for_user(db, user_id)
    return profile


async def _get_or_create_status(db: AsyncSession, user_id: uuid.UUID) -> BraiderOnboardingStatus:
    status = await braiders_repo.get_onboarding_status_by_user_id(db, user_id)
    if status is None:
        status = await braiders_repo.create_onboarding_status_for_user(db, user_id)
    return status


async def _get_or_create_location(
    db: AsyncSession, braider_id: uuid.UUID
) -> BraiderServiceLocation:
    location = await location_repo.get_by_braider_id(db, braider_id)
    if location is None:
        location = await location_repo.create_for_braider(db, braider_id)
    return location


def _to_response(location: BraiderServiceLocation) -> ServiceLocationResponse:
    return ServiceLocationResponse(
        location_type=location.location_type,
        salon_name=location.salon_name,
        address_line1=location.address_line1,
        address_line2=location.address_line2,
        city=location.city,
        postal_code=location.postal_code,
        country=location.country,
        latitude=location.latitude,
        longitude=location.longitude,
        offers_mobile=location.offers_mobile,
        travel_radius_km=location.travel_radius_km,
        travel_fee=location.travel_fee,
        is_complete=is_service_location_complete(location),
    )


async def get_service_location(db: AsyncSession, user_id: uuid.UUID) -> ServiceLocationResponse:
    profile = await _get_or_create_profile(db, user_id)
    location = await _get_or_create_location(db, profile.id)
    await db.commit()
    return _to_response(location)


async def update_service_location(
    db: AsyncSession, user_id: uuid.UUID, *, data: ServiceLocationUpdateRequest
) -> ServiceLocationResponse:
    profile = await _get_or_create_profile(db, user_id)
    location = await _get_or_create_location(db, profile.id)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(location, field, LocationType(value) if field == "location_type" and value else value)

    # A salon_name lingering from a previous SALON selection would be
    # confusing once location_type no longer says SALON - normalize it away
    # instead of requiring the client to explicitly clear it every time.
    if location.location_type != LocationType.SALON:
        location.salon_name = None

    # Same idea: a travel radius/fee shouldn't survive turning mobile off.
    if not location.offers_mobile:
        location.travel_radius_km = None
        location.travel_fee = None

    await db.flush()

    status = await _get_or_create_status(db, user_id)
    recompute_service_location_completion(location, status)
    await db.commit()

    return _to_response(location)
