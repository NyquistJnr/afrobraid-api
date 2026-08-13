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


async def _customer_headers(db_session: AsyncSession) -> dict:
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    return {"Authorization": f"Bearer {token}"}


async def test_create_booking_with_paypal_provider(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session, base_price="180.00", country="AT")
    headers = await _customer_headers(db_session)

    calc_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    calc = calc_resp.json()["data"]
    starts_at = datetime.now(UTC) + timedelta(hours=10)

    resp = await client.post(
        BOOKINGS_URL,
        json={
            "booking_calculation_id": calc["id"],
            "starts_at": starts_at.isoformat(),
            "terms_accepted": True,
            "payment_provider": "PAYPAL",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "PENDING_PAYMENT"
    assert len(data["payments"]) == 1

    payment = data["payments"][0]
    assert payment["provider"] == "PAYPAL"
    assert payment["client_secret"] is None
    assert payment["paypal_order_id"] is not None
    assert payment["paypal_order_id"].startswith("paypal_order_test_")


async def test_create_booking_defaults_to_stripe_provider(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session, base_price="180.00", country="AT")
    headers = await _customer_headers(db_session)

    calc_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    calc = calc_resp.json()["data"]
    starts_at = datetime.now(UTC) + timedelta(hours=10)

    resp = await client.post(
        BOOKINGS_URL,
        json={
            "booking_calculation_id": calc["id"],
            "starts_at": starts_at.isoformat(),
            "terms_accepted": True,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    payment = resp.json()["data"]["payments"][0]
    assert payment["provider"] == "STRIPE"
    assert payment["client_secret"] is not None
    assert payment["paypal_order_id"] is None
