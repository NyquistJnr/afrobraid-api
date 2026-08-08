from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"
TODAY_COUNT_URL = "/api/v1/admin/bookings/today-count"


async def _create_booking(
    client: AsyncClient, braider: dict, customer_headers: dict, *, hours_from_now: int
) -> None:
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


async def test_today_count_reflects_bookings_created_today(
    client: AsyncClient, db_session: AsyncSession
):
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    baseline = await client.get(TODAY_COUNT_URL, headers=admin_headers)
    assert baseline.status_code == 200, baseline.text
    baseline_count = baseline.json()["data"]

    braider = await create_bookable_braider(db_session)
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    await _create_booking(client, braider, customer_headers, hours_from_now=10)
    await _create_booking(client, braider, customer_headers, hours_from_now=30)

    after = await client.get(TODAY_COUNT_URL, headers=admin_headers)
    assert after.status_code == 200, after.text
    assert after.json()["data"] == baseline_count + 2


async def test_today_count_requires_admin(client: AsyncClient, db_session: AsyncSession):
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    resp = await client.get(TODAY_COUNT_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_today_count_needs_no_params(client: AsyncClient, db_session: AsyncSession):
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    resp = await client.get(TODAY_COUNT_URL, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], int)
