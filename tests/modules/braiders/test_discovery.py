from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders.models import BraiderOnboardingStatus, BraiderProfile
from app.modules.braiders.offerings.models import BraiderStyle
from app.modules.braiders.portfolio.models import PortfolioImage
from app.modules.braiders.service_location.models import BraiderServiceLocation, LocationType
from app.modules.styles.models import Style
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token

pytestmark = pytest.mark.asyncio

# Lagos-ish coordinates, ~5km apart.
LAT_NEAR, LNG_NEAR = 6.5244, 3.3792
LAT_FAR, LNG_FAR = 9.0765, 7.3986  # Abuja, ~500km away


async def _make_completed_braider(
    db_session: AsyncSession,
    *,
    business_name: str,
    lat: float,
    lng: float,
    location_type: LocationType = LocationType.SALON,
) -> BraiderProfile:
    user, _ = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    profile = BraiderProfile(user_id=user.id, business_name=business_name, bio_en="Great braids")
    db_session.add(profile)
    await db_session.flush()

    db_session.add(
        BraiderServiceLocation(
            braider_id=profile.id,
            location_type=location_type,
            salon_name="The Studio",
            address_line1="123 Main St",
            city="Lagos",
            country="NG",
            latitude=lat,
            longitude=lng,
        )
    )
    db_session.add(
        BraiderOnboardingStatus(user_id=user.id, completed_at=datetime(2026, 1, 1, tzinfo=UTC))
    )
    db_session.add(
        PortfolioImage(braider_id=profile.id, object_key="braiders/x/portfolio/1.jpg", position=0)
    )
    await db_session.commit()
    return profile


async def test_search_by_location_and_detail_and_style(
    client: AsyncClient, db_session: AsyncSession
):
    near = await _make_completed_braider(
        db_session, business_name="Near Braids", lat=LAT_NEAR, lng=LNG_NEAR
    )
    far = await _make_completed_braider(
        db_session,
        business_name="Far Braids",
        lat=LAT_FAR,
        lng=LNG_FAR,
        location_type=LocationType.HOME_STUDIO,
    )

    style = Style(slug="knotless-braids", name_en="Knotless Braids", is_active=True)
    db_session.add(style)
    await db_session.flush()
    db_session.add(
        BraiderStyle(braider_id=near.id, style_id=style.id, base_price=150, duration_minutes=240)
    )
    await db_session.commit()

    # 1. Search near LAT_NEAR/LNG_NEAR with a tight radius - only "near" should show.
    resp = await client.get(
        f"/api/v1/braiders?lat={LAT_NEAR}&lng={LNG_NEAR}&radius_km=50"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    ids = [item["id"] for item in body["items"]]
    assert str(near.id) in ids
    assert str(far.id) not in ids
    near_item = next(i for i in body["items"] if i["id"] == str(near.id))
    assert near_item["distance_km"] is not None and near_item["distance_km"] < 5
    assert near_item["cover_photo_url"] is not None

    # 2. Wide radius picks up both, sorted nearest first.
    resp = await client.get(f"/api/v1/braiders?lat={LAT_NEAR}&lng={LNG_NEAR}&radius_km=2000")
    body = resp.json()["data"]
    ids = [item["id"] for item in body["items"]]
    assert ids.index(str(near.id)) < ids.index(str(far.id))

    # 3. Style filter - only the braider offering that style shows, with matched_style.
    resp = await client.get(f"/api/v1/braiders?style_id={style.id}")
    body = resp.json()["data"]
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(near.id)
    assert body["items"][0]["matched_style"]["name"] == "Knotless Braids"
    assert body["items"][0]["matched_style"]["base_price"] == "150.00"

    # Style slug does the same thing.
    resp = await client.get(f"/api/v1/braiders?style_slug={style.slug}")
    assert resp.json()["data"]["items"][0]["id"] == str(near.id)

    # Unknown slug -> empty page, not an error.
    resp = await client.get("/api/v1/braiders?style_slug=does-not-exist")
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []

    # 4. Detail endpoint - full profile, salon address visible.
    resp = await client.get(f"/api/v1/braiders/{near.id}")
    assert resp.status_code == 200, resp.text
    detail = resp.json()["data"]
    assert detail["business_name"] == "Near Braids"
    assert detail["bio"] == "Great braids"
    assert detail["location"]["address_line1"] == "123 Main St"
    assert len(detail["styles"]) == 1
    assert detail["styles"][0]["name"] == "Knotless Braids"
    assert len(detail["portfolio"]) == 1

    # 5. Home-studio detail - address withheld, city still shown.
    resp = await client.get(f"/api/v1/braiders/{far.id}")
    detail = resp.json()["data"]
    assert detail["location"]["address_line1"] is None
    assert detail["location"]["city"] == "Lagos"

    # 6. lat without lng -> 400.
    resp = await client.get(f"/api/v1/braiders?lat={LAT_NEAR}")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SEARCH_LOCATION"

    # 7. Unknown braider id -> 404.
    resp = await client.get("/api/v1/braiders/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "BRAIDER_NOT_FOUND"


async def test_incomplete_onboarding_braider_is_hidden(
    client: AsyncClient, db_session: AsyncSession
):
    user, _ = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    profile = BraiderProfile(user_id=user.id, business_name="Not Ready Yet")
    db_session.add(profile)
    await db_session.flush()
    db_session.add(BraiderOnboardingStatus(user_id=user.id, completed_at=None))
    await db_session.commit()

    resp = await client.get("/api/v1/braiders")
    ids = [item["id"] for item in resp.json()["data"]["items"]]
    assert str(profile.id) not in ids

    resp = await client.get(f"/api/v1/braiders/{profile.id}")
    assert resp.status_code == 404
