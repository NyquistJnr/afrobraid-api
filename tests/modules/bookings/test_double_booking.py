import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders.availability.models import BraiderAvailabilitySettings
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"


async def _customer_headers(db_session: AsyncSession) -> dict:
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    return {"Authorization": f"Bearer {token}"}


async def _create_calculation(client: AsyncClient, braider: dict) -> dict:
    resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _book(client: AsyncClient, headers: dict, calc: dict, starts_at: datetime):
    return await client.post(
        BOOKINGS_URL,
        json={
            "booking_calculation_id": calc["id"],
            "starts_at": starts_at.isoformat(),
            "terms_accepted": True,
        },
        headers=headers,
    )


async def test_overlapping_bookings_second_one_conflicts(client: AsyncClient, db_session: AsyncSession):
    # duration_minutes=240 (4h) by default.
    braider = await create_bookable_braider(db_session, base_price="180.00", country="AT")
    headers = await _customer_headers(db_session)
    starts_at = datetime.now(UTC) + timedelta(hours=10)

    calc_a = await _create_calculation(client, braider)
    resp_a = await _book(client, headers, calc_a, starts_at)
    assert resp_a.status_code == 201, resp_a.text

    # Overlaps the first booking's [starts_at, starts_at+4h) window.
    calc_b = await _create_calculation(client, braider)
    resp_b = await _book(client, headers, calc_b, starts_at + timedelta(hours=1))
    assert resp_b.status_code == 409, resp_b.text
    assert resp_b.json()["error"]["code"] == "BOOKING_SLOT_UNAVAILABLE"


async def test_adjacent_bookings_with_zero_buffer_both_succeed(
    client: AsyncClient, db_session: AsyncSession
):
    # create_bookable_braider doesn't create a BraiderAvailabilitySettings
    # row, so bookings/service.py falls back to buffer_minutes=0 - back-to-
    # back appointments with no gap must both be bookable.
    braider = await create_bookable_braider(db_session, base_price="180.00", country="AT")
    headers = await _customer_headers(db_session)
    starts_at = datetime.now(UTC) + timedelta(hours=10)

    calc_a = await _create_calculation(client, braider)
    resp_a = await _book(client, headers, calc_a, starts_at)
    assert resp_a.status_code == 201, resp_a.text

    # Starts exactly when the first one ends (4h duration) - must not collide.
    calc_b = await _create_calculation(client, braider)
    resp_b = await _book(client, headers, calc_b, starts_at + timedelta(hours=4))
    assert resp_b.status_code == 201, resp_b.text


async def test_adjacent_bookings_with_nonzero_buffer_conflict(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(db_session, base_price="180.00", country="AT")
    db_session.add(BraiderAvailabilitySettings(braider_id=braider["braider_id"], buffer_minutes=30))
    await db_session.commit()

    headers = await _customer_headers(db_session)
    starts_at = datetime.now(UTC) + timedelta(hours=10)

    calc_a = await _create_calculation(client, braider)
    resp_a = await _book(client, headers, calc_a, starts_at)
    assert resp_a.status_code == 201, resp_a.text

    # Same pair of times that succeeded with buffer=0 now collides because
    # the first booking's blocked_until extends 30 minutes past its ends_at.
    calc_b = await _create_calculation(client, braider)
    resp_b = await _book(client, headers, calc_b, starts_at + timedelta(hours=4))
    assert resp_b.status_code == 409, resp_b.text
    assert resp_b.json()["error"]["code"] == "BOOKING_SLOT_UNAVAILABLE"


async def test_concurrent_creates_for_same_slot_exactly_one_succeeds(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(db_session, base_price="180.00", country="AT")
    headers = await _customer_headers(db_session)
    starts_at = datetime.now(UTC) + timedelta(hours=10)

    calc_a = await _create_calculation(client, braider)
    calc_b = await _create_calculation(client, braider)

    resp_a, resp_b = await asyncio.gather(
        _book(client, headers, calc_a, starts_at),
        _book(client, headers, calc_b, starts_at),
    )

    statuses = sorted([resp_a.status_code, resp_b.status_code])
    assert statuses == [201, 409]
