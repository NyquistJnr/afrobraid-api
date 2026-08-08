import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.enums import BookingStatus
from app.modules.bookings.models import Booking
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
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"


async def _confirmed_booking(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    braider: dict,
    customer_headers: dict,
    hours_from_now: int = 10,
) -> None:
    """Mirrors tests/modules/reviews/test_reviews.py's helper of the same
    shape: drives the real checkout flow, then flips the resulting booking
    straight to CONFIRMED in place of a webhook-driven payment success."""
    calc_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    assert calc_resp.status_code == 201, calc_resp.text
    calc = calc_resp.json()["data"]

    book_resp = await client.post(
        BOOKINGS_URL,
        json={
            "booking_calculation_id": calc["id"],
            "starts_at": (datetime.now(UTC) + timedelta(hours=hours_from_now)).isoformat(),
            "terms_accepted": True,
        },
        headers=customer_headers,
    )
    assert book_resp.status_code == 201, book_resp.text
    booking_id = uuid.UUID(book_resp.json()["data"]["id"])

    booking = await db_session.get(Booking, booking_id)
    booking.status = BookingStatus.CONFIRMED
    await db_session.commit()


async def _add_review(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    braider: dict,
    rating: int,
    hours_from_now: int = 10,
) -> None:
    """One eligible, rated review from a fresh customer - average_rating
    reflects immediately, no admin approval needed (only the comment is
    moderated, see test_reviews.py)."""
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    customer_headers = {"Authorization": f"Bearer {token}"}
    await _confirmed_booking(
        client,
        db_session,
        braider=braider,
        customer_headers=customer_headers,
        hours_from_now=hours_from_now,
    )

    resp = await client.put(
        f"/api/v1/braiders/{braider['braider_id']}/reviews/me",
        json={"rating": rating},
        headers=customer_headers,
    )
    assert resp.status_code == 200, resp.text

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
    onboarded_at: datetime | None = None,
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
    onboarded_at = onboarded_at or datetime(2026, 1, 1, tzinfo=UTC)
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
            completed_at=onboarded_at,
        )
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
    # Salon location -> full address returned in the list view too.
    assert near_item["location"]["address_line1"] == "123 Main St"
    assert near_item["location"]["salon_name"] == "The Studio"
    assert near_item["location"]["city"] == "Lagos"
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
    # Home-studio -> exact address withheld in the list view, city still shown.
    assert far_item["location"]["address_line1"] is None
    assert far_item["location"]["city"] == "Lagos"

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


async def test_search_by_location_without_radius_defaults_to_100km(
    client: AsyncClient, db_session: AsyncSession
):
    near = await _make_completed_braider(
        db_session, business_name="Near Braids", lat=LAT_NEAR, lng=LNG_NEAR
    )
    far = await _make_completed_braider(
        db_session, business_name="Far Braids", lat=LAT_FAR, lng=LNG_FAR
    )

    # No radius_km given - should still exclude the ~500km-away braider
    # instead of returning every braider worldwide sorted by distance.
    resp = await client.get(f"/api/v1/braiders?lat={LAT_NEAR}&lng={LNG_NEAR}")
    assert resp.status_code == 200, resp.text
    ids = {item["id"] for item in resp.json()["data"]["items"]}
    assert str(near.id) in ids
    assert str(far.id) not in ids


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


async def test_payment_setup_pending_braider_is_hidden(
    client: AsyncClient, db_session: AsyncSession
):
    """Every onboarding step, payment setup included, is required to be
    publicly listed - a braider who can't get paid yet shouldn't be
    bookable."""
    user, _ = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    profile = BraiderProfile(user_id=user.id, business_name="Payment Pending")
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
            payment_setup_completed_at=None,
            completed_at=None,
        )
    )
    await db_session.commit()

    resp = await client.get("/api/v1/braiders")
    ids = [item["id"] for item in resp.json()["data"]["items"]]
    assert str(profile.id) not in ids

    resp = await client.get(f"/api/v1/braiders/{profile.id}")
    assert resp.status_code == 404


async def test_search_by_is_mobile(client: AsyncClient, db_session: AsyncSession):
    mobile = await _make_completed_braider(
        db_session, business_name="Mobile Braids", lat=LAT_NEAR, lng=LNG_NEAR
    )
    location_result = await db_session.execute(
        select(BraiderServiceLocation).where(BraiderServiceLocation.braider_id == mobile.id)
    )
    mobile_location = location_result.scalar_one()
    mobile_location.offers_mobile = True
    mobile_location.travel_radius_km = 20

    salon_only = await _make_completed_braider(
        db_session, business_name="Salon Only", lat=LAT_NEAR, lng=LNG_NEAR
    )
    await db_session.commit()

    resp = await client.get("/api/v1/braiders?is_mobile=true")
    ids = {item["id"] for item in resp.json()["data"]["items"]}
    assert str(mobile.id) in ids
    assert str(salon_only.id) not in ids

    resp = await client.get("/api/v1/braiders?is_mobile=false")
    ids = {item["id"] for item in resp.json()["data"]["items"]}
    assert str(salon_only.id) in ids
    assert str(mobile.id) not in ids


async def test_search_by_price_range(client: AsyncClient, db_session: AsyncSession):
    cheap = await _make_completed_braider(
        db_session, business_name="Cheap Braids", lat=LAT_NEAR, lng=LNG_NEAR
    )
    pricey = await _make_completed_braider(
        db_session, business_name="Pricey Braids", lat=LAT_NEAR, lng=LNG_NEAR
    )

    style = Style(slug="box-braids", name_en="Box Braids", is_active=True)
    db_session.add(style)
    await db_session.flush()
    db_session.add(BraiderStyle(braider_id=cheap.id, style_id=style.id, base_price=50))
    db_session.add(BraiderStyle(braider_id=pricey.id, style_id=style.id, base_price=500))
    await db_session.commit()

    resp = await client.get("/api/v1/braiders?min_amount=100&max_amount=600")
    ids = {item["id"] for item in resp.json()["data"]["items"]}
    assert str(pricey.id) in ids
    assert str(cheap.id) not in ids

    resp = await client.get("/api/v1/braiders?max_amount=100")
    ids = {item["id"] for item in resp.json()["data"]["items"]}
    assert str(cheap.id) in ids
    assert str(pricey.id) not in ids

    resp = await client.get("/api/v1/braiders?min_amount=600&max_amount=100")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SEARCH_PRICE_RANGE"


async def test_search_by_country_code(client: AsyncClient, db_session: AsyncSession):
    ng_braider = await _make_completed_braider(
        db_session, business_name="Lagos Braids", lat=LAT_NEAR, lng=LNG_NEAR
    )

    resp = await client.get("/api/v1/braiders?country_code=NG")
    ids = {item["id"] for item in resp.json()["data"]["items"]}
    assert str(ng_braider.id) in ids

    resp = await client.get("/api/v1/braiders?country_code=us")
    ids = {item["id"] for item in resp.json()["data"]["items"]}
    assert str(ng_braider.id) not in ids


async def test_search_styles_capped_at_five(client: AsyncClient, db_session: AsyncSession):
    braider = await _make_completed_braider(
        db_session, business_name="Many Styles", lat=LAT_NEAR, lng=LNG_NEAR
    )
    for i in range(7):
        style = Style(slug=f"style-{i}", name_en=f"Style {i}", is_active=True)
        db_session.add(style)
        await db_session.flush()
        db_session.add(BraiderStyle(braider_id=braider.id, style_id=style.id, base_price=50))
    await db_session.commit()

    resp = await client.get("/api/v1/braiders")
    item = next(i for i in resp.json()["data"]["items"] if i["id"] == str(braider.id))
    assert len(item["styles"]) == 5


async def test_search_by_rating_range(client: AsyncClient, db_session: AsyncSession):
    high_rated = await create_bookable_braider(db_session, business_name="High Rated")
    low_rated = await create_bookable_braider(db_session, business_name="Low Rated")
    await _add_review(client, db_session, braider=high_rated, rating=5)
    await _add_review(client, db_session, braider=low_rated, rating=2)

    resp = await client.get("/api/v1/braiders?min_rate=4")
    ids = {item["id"] for item in resp.json()["data"]["items"]}
    assert str(high_rated["braider_id"]) in ids
    assert str(low_rated["braider_id"]) not in ids

    resp = await client.get("/api/v1/braiders?max_rate=3")
    ids = {item["id"] for item in resp.json()["data"]["items"]}
    assert str(low_rated["braider_id"]) in ids
    assert str(high_rated["braider_id"]) not in ids

    resp = await client.get("/api/v1/braiders?min_rate=4&max_rate=1")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SEARCH_RATING_RANGE"


async def test_new_braiders_list(client: AsyncClient, db_session: AsyncSession):
    now = datetime.now(UTC)
    fresh = await _make_completed_braider(
        db_session,
        business_name="Fresh Braids",
        lat=LAT_NEAR,
        lng=LNG_NEAR,
        onboarded_at=now - timedelta(days=5),
    )
    stale = await _make_completed_braider(
        db_session,
        business_name="Stale Braids",
        lat=LAT_NEAR,
        lng=LNG_NEAR,
        onboarded_at=now - timedelta(days=60),
    )

    resp = await client.get("/api/v1/braiders/new")
    assert resp.status_code == 200, resp.text
    ids = [item["id"] for item in resp.json()["data"]["items"]]
    assert str(fresh.id) in ids
    assert str(stale.id) not in ids


async def test_top_rated_braiders_list(client: AsyncClient, db_session: AsyncSession):
    well_reviewed = await create_bookable_braider(db_session, business_name="Well Reviewed")
    for i in range(3):
        # Default duration is 4h - space bookings out so they don't overlap.
        await _add_review(
            client, db_session, braider=well_reviewed, rating=5, hours_from_now=10 + i * 5
        )

    # A single review is enough to qualify (min rating_count threshold is 1) -
    # an early-stage catalog shouldn't have an empty top-rated list.
    once_reviewed = await create_bookable_braider(db_session, business_name="Once Reviewed")
    await _add_review(client, db_session, braider=once_reviewed, rating=4)

    # Never reviewed at all - genuinely excluded, nothing to rank on.
    unrated = await create_bookable_braider(db_session, business_name="Unrated")

    resp = await client.get("/api/v1/braiders/top-rated")
    assert resp.status_code == 200, resp.text
    ids = [item["id"] for item in resp.json()["data"]["items"]]
    assert str(well_reviewed["braider_id"]) in ids
    assert str(once_reviewed["braider_id"]) in ids
    assert str(unrated["braider_id"]) not in ids
    # Higher average ranks first.
    assert ids.index(str(well_reviewed["braider_id"])) < ids.index(str(once_reviewed["braider_id"]))


async def test_trending_braiders_list(client: AsyncClient, db_session: AsyncSession):
    busy = await create_bookable_braider(db_session, business_name="Busy Braids", country="AT")
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    customer_headers = {"Authorization": f"Bearer {token}"}
    await _confirmed_booking(client, db_session, braider=busy, customer_headers=customer_headers)

    quiet = await create_bookable_braider(db_session, business_name="Quiet Braids", country="AT")

    resp = await client.get("/api/v1/braiders/trending?country_code=AT")
    assert resp.status_code == 200, resp.text
    ids = [item["id"] for item in resp.json()["data"]["items"]]
    assert str(busy["braider_id"]) in ids
    assert str(quiet["braider_id"]) not in ids

    # No country_code and no lat/lng - "trending" needs a scope.
    resp = await client.get("/api/v1/braiders/trending")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_TRENDING_LOCATION"


async def test_recommended_braiders_list(client: AsyncClient, db_session: AsyncSession):
    now = datetime.now(UTC)
    top_rated_established = await _make_completed_braider(
        db_session,
        business_name="Established Star",
        lat=LAT_NEAR,
        lng=LNG_NEAR,
        onboarded_at=now - timedelta(days=200),
    )
    top_rated_established.average_rating = 5
    top_rated_established.rating_count = 10

    new_unrated = await _make_completed_braider(
        db_session,
        business_name="Brand New",
        lat=LAT_NEAR,
        lng=LNG_NEAR,
        onboarded_at=now - timedelta(days=1),
    )

    old_unrated = await _make_completed_braider(
        db_session,
        business_name="Old And Unrated",
        lat=LAT_NEAR,
        lng=LNG_NEAR,
        onboarded_at=now - timedelta(days=200),
    )
    await db_session.commit()

    resp = await client.get("/api/v1/braiders/recommended")
    assert resp.status_code == 200, resp.text
    ids = [item["id"] for item in resp.json()["data"]["items"]]
    assert str(top_rated_established.id) in ids
    assert str(new_unrated.id) in ids
    assert str(old_unrated.id) in ids
    # Highly rated ranks first; the "new" boost puts the fresh, unrated
    # braider ahead of the equally-unrated but stale one.
    assert (
        ids.index(str(top_rated_established.id))
        < ids.index(str(new_unrated.id))
        < ids.index(str(old_unrated.id))
    )
