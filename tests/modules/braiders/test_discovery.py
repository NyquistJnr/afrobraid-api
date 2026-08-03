from datetime import UTC, date, datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders.availability.models import (
    AvailabilityExceptionType,
    BraiderAvailabilityException,
    BraiderWeeklyAvailability,
    DayOfWeek,
)
from app.modules.braiders.models import BraiderOnboardingStatus, BraiderProfile
from app.modules.braiders.offerings.models import BraiderStyle
from app.modules.braiders.portfolio.models import PortfolioImage
from app.modules.braiders.service_location.models import BraiderServiceLocation, LocationType
from app.modules.styles.models import Style
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token

pytestmark = pytest.mark.asyncio

_WEEKDAY_TO_DAY_OF_WEEK = [
    DayOfWeek.MONDAY,
    DayOfWeek.TUESDAY,
    DayOfWeek.WEDNESDAY,
    DayOfWeek.THURSDAY,
    DayOfWeek.FRIDAY,
    DayOfWeek.SATURDAY,
    DayOfWeek.SUNDAY,
]

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
    resp = await client.get(f"/api/v1/braiders?lat={LAT_NEAR}&lng={LNG_NEAR}&radius_km=50")
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    ids = [item["id"] for item in body["items"]]
    assert str(near.id) in ids
    assert str(far.id) not in ids
    near_item = next(i for i in body["items"] if i["id"] == str(near.id))
    assert near_item["distance_km"] is not None and near_item["distance_km"] < 5
    assert near_item["cover_photo_url"] is not None
    # No style filter applied -> matched_style is null, but the full menu is
    # still there so the frontend isn't left with nothing to show.
    assert near_item["matched_style"] is None
    assert near_item["styles"] == [
        {
            "style_id": str(style.id),
            "name": "Knotless Braids",
            "base_price": "150.00",
            "duration_minutes": 240,
        }
    ]

    # 2. Wide radius picks up both, sorted nearest first.
    resp = await client.get(f"/api/v1/braiders?lat={LAT_NEAR}&lng={LNG_NEAR}&radius_km=2000")
    body = resp.json()["data"]
    ids = [item["id"] for item in body["items"]]
    assert ids.index(str(near.id)) < ids.index(str(far.id))
    far_item = next(i for i in body["items"] if i["id"] == str(far.id))
    assert far_item["styles"] == []

    # 3. Style filter - only the braider offering that style shows, with matched_style.
    resp = await client.get(f"/api/v1/braiders?style_id={style.id}")
    body = resp.json()["data"]
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(near.id)
    assert body["items"][0]["matched_style"]["name"] == "Knotless Braids"
    assert body["items"][0]["matched_style"]["base_price"] == "150.00"
    # matched_style highlights the searched-for style, styles still lists the full menu.
    assert len(body["items"][0]["styles"]) == 1

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


async def test_search_by_availability_date_range(client: AsyncClient, db_session: AsyncSession):
    anchor = date.today() + timedelta(days=7)
    anchor_dow = _WEEKDAY_TO_DAY_OF_WEEK[anchor.weekday()]
    off_day = anchor - timedelta(days=1)

    weekly_open = await _make_completed_braider(
        db_session, business_name="Weekly Open", lat=LAT_NEAR, lng=LNG_NEAR
    )
    db_session.add(
        BraiderWeeklyAvailability(
            braider_id=weekly_open.id,
            day_of_week=anchor_dow,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
    )

    closed_via_exception = await _make_completed_braider(
        db_session, business_name="Closed That Day", lat=LAT_NEAR, lng=LNG_NEAR
    )
    db_session.add(
        BraiderWeeklyAvailability(
            braider_id=closed_via_exception.id,
            day_of_week=anchor_dow,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
    )
    db_session.add(
        BraiderAvailabilityException(
            braider_id=closed_via_exception.id,
            date=anchor,
            exception_type=AvailabilityExceptionType.CLOSED,
        )
    )

    custom_hours_only = await _make_completed_braider(
        db_session, business_name="Custom Hours Only", lat=LAT_NEAR, lng=LNG_NEAR
    )
    db_session.add(
        BraiderAvailabilityException(
            braider_id=custom_hours_only.id,
            date=anchor,
            exception_type=AvailabilityExceptionType.CUSTOM_HOURS,
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
    )

    no_availability_at_all = await _make_completed_braider(
        db_session, business_name="No Availability", lat=LAT_NEAR, lng=LNG_NEAR
    )
    await db_session.commit()

    # Querying exactly `anchor`: weekly_open shows, closed_via_exception is
    # excluded despite having a weekly window (the exception overrides it),
    # custom_hours_only shows via its one-off exception, no_availability never shows.
    resp = await client.get(f"/api/v1/braiders?date_from={anchor}&date_to={anchor}")
    assert resp.status_code == 200, resp.text
    ids = {item["id"] for item in resp.json()["data"]["items"]}
    assert str(weekly_open.id) in ids
    assert str(closed_via_exception.id) not in ids
    assert str(custom_hours_only.id) in ids
    assert str(no_availability_at_all.id) not in ids

    # Querying `off_day` (a different weekday, no matching window/exception there):
    # only weekly_open's weekly pattern doesn't cover it, so none of our fixtures show.
    resp = await client.get(f"/api/v1/braiders?date_from={off_day}&date_to={off_day}")
    ids = {item["id"] for item in resp.json()["data"]["items"]}
    assert str(weekly_open.id) not in ids
    assert str(closed_via_exception.id) not in ids
    assert str(custom_hours_only.id) not in ids

    # Validation: only one of date_from/date_to given.
    resp = await client.get(f"/api/v1/braiders?date_from={anchor}")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SEARCH_DATE_RANGE"

    # Validation: date_to before date_from.
    resp = await client.get(f"/api/v1/braiders?date_from={anchor}&date_to={off_day}")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SEARCH_DATE_RANGE"

    # Validation: range too wide (> 90 days).
    too_far = anchor + timedelta(days=91)
    resp = await client.get(f"/api/v1/braiders?date_from={anchor}&date_to={too_far}")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SEARCH_DATE_RANGE"
