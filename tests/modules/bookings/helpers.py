import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders.models import BraiderOnboardingStatus, BraiderProfile
from app.modules.braiders.offerings.models import (
    BraiderStyle,
    BraiderStyleAddon,
    BraiderStyleVariation,
)
from app.modules.braiders.service_location.models import BraiderServiceLocation, LocationType
from app.modules.styles.models import AddOn, Style, StyleVariation
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token


async def create_bookable_braider(
    db_session: AsyncSession,
    *,
    business_name: str = "Test Braids",
    base_price: str = "180.00",
    duration_minutes: int | None = 240,
    with_variation: bool = False,
    variation_price: str = "200.00",
    with_addon: bool = False,
    addon_price: str = "20.00",
    addon_required: bool = False,
    offers_mobile: bool = False,
    travel_fee: str | None = "15.00",
    country: str = "DE",
) -> dict:
    """Builds a publicly-visible, bookable braider (every onboarding step
    complete, payment setup included - see
    braiders.discovery.repository._REQUIRED_ONBOARDING_FIELDS) with one
    offered style, directly via the ORM, mirroring
    tests/modules/braiders/test_discovery.py's _make_completed_braider."""
    user, _ = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    profile = BraiderProfile(user_id=user.id, business_name=business_name, bio_en="Great braids")
    db_session.add(profile)
    await db_session.flush()

    onboarded_at = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.add(
        BraiderOnboardingStatus(
            user_id=user.id,
            business_info_completed_at=onboarded_at,
            phone_verification_completed_at=onboarded_at,
            veriff_completed_at=onboarded_at,
            service_type_completed_at=onboarded_at,
            portfolio_completed_at=onboarded_at,
            service_location_completed_at=onboarded_at,
            availability_completed_at=onboarded_at,
            payment_setup_completed_at=onboarded_at,
        )
    )

    db_session.add(
        BraiderServiceLocation(
            braider_id=profile.id,
            location_type=LocationType.SALON,
            salon_name="The Studio",
            address_line1="123 Main St",
            city="Berlin",
            country=country,
            offers_mobile=offers_mobile,
            travel_radius_km=20 if offers_mobile else None,
            travel_fee=Decimal(travel_fee) if (offers_mobile and travel_fee is not None) else None,
        )
    )

    style = Style(slug=f"style-{uuid.uuid4().hex[:10]}", name_en="Knotless Braids", is_active=True)
    db_session.add(style)
    await db_session.flush()

    braider_style = BraiderStyle(
        braider_id=profile.id,
        style_id=style.id,
        base_price=Decimal(base_price),
        duration_minutes=duration_minutes,
    )
    db_session.add(braider_style)
    await db_session.flush()

    result: dict = {
        "user": user,
        "profile": profile,
        "braider_id": profile.id,
        "style_id": style.id,
        "braider_style_id": braider_style.id,
        "braider_style_variation_id": None,
        "style_variation_id": None,
        "braider_style_addon_id": None,
        "addon_id": None,
    }

    if with_variation:
        variation = StyleVariation(style_id=style.id, name_en="Mid-back length", is_active=True)
        db_session.add(variation)
        await db_session.flush()
        braider_variation = BraiderStyleVariation(
            braider_style_id=braider_style.id,
            style_variation_id=variation.id,
            price=Decimal(variation_price),
        )
        db_session.add(braider_variation)
        await db_session.flush()
        result["style_variation_id"] = variation.id
        result["braider_style_variation_id"] = braider_variation.id

    if with_addon:
        addon = AddOn(slug=f"addon-{uuid.uuid4().hex[:10]}", name_en="Beads", is_active=True)
        db_session.add(addon)
        await db_session.flush()
        braider_addon = BraiderStyleAddon(
            braider_style_id=braider_style.id,
            addon_id=addon.id,
            price=Decimal(addon_price),
            is_required=addon_required,
        )
        db_session.add(braider_addon)
        await db_session.flush()
        result["addon_id"] = addon.id
        result["braider_style_addon_id"] = braider_addon.id

    await db_session.commit()
    return result
