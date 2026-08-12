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
ADMIN_BOOKINGS_URL = "/api/v1/admin/bookings"
ADMIN_PAYMENTS_URL = "/api/v1/admin/payments"


async def _create_booking(client: AsyncClient, db_session: AsyncSession) -> dict:
    braider = await create_bookable_braider(
        db_session, business_name="Royal Braids", base_price="180.00", country="AT"
    )
    customer, customer_token = await create_user_with_token(
        db_session, user_type=UserType.CUSTOMER, email="customer@example.com"
    )
    headers = {"Authorization": f"Bearer {customer_token}"}

    calc_resp = await client.post(
        CALC_URL,
        json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])},
    )
    assert calc_resp.status_code == 201, calc_resp.text
    calc = calc_resp.json()["data"]

    starts_at = datetime.now(UTC) + timedelta(hours=10)
    booking_resp = await client.post(
        BOOKINGS_URL,
        json={
            "booking_calculation_id": calc["id"],
            "starts_at": starts_at.isoformat(),
            "terms_accepted": True,
        },
        headers=headers,
    )
    assert booking_resp.status_code == 201, booking_resp.text
    return {
        "booking": booking_resp.json()["data"],
        "braider": braider,
        "customer": customer,
        "starts_at": starts_at,
    }


async def test_admin_can_list_search_filter_and_get_booking(
    client: AsyncClient, db_session: AsyncSession
):
    created = await _create_booking(client, db_session)
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    headers = {"Authorization": f"Bearer {admin_token}"}

    list_resp = await client.get(
        ADMIN_BOOKINGS_URL,
        params={
            "search": "Royal",
            "status": "PENDING_PAYMENT",
            "country": "AT",
            "payment_schedule": "FULL_UPFRONT",
            "date_from": created["starts_at"].date().isoformat(),
            "date_to": created["starts_at"].date().isoformat(),
        },
        headers=headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    data = list_resp.json()["data"]
    assert data["total_items"] == 1
    item = data["items"][0]
    assert item["id"] == created["booking"]["id"]
    assert item["customer_id"] == str(created["customer"].id)
    assert item["customer_email"] == "customer@example.com"
    assert item["braider_id"] == str(created["braider"]["braider_id"])
    assert item["braider_name"] == "Royal Braids"

    detail_resp = await client.get(
        f"{ADMIN_BOOKINGS_URL}/{created['booking']['id']}", headers=headers
    )
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()["data"]
    assert detail["reference"] == created["booking"]["reference"]
    assert detail["customer_email"] == "customer@example.com"
    assert detail["payments"][0]["purpose"] == "FULL"
    assert detail["payments"][0]["stripe_payment_intent_id"].startswith("pi_test_")
    assert detail["items"]


async def test_admin_payments_list_supports_core_filters(
    client: AsyncClient, db_session: AsyncSession
):
    created = await _create_booking(client, db_session)
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.get(
        ADMIN_PAYMENTS_URL,
        params={
            "search": created["booking"]["reference"],
            "purpose": "FULL",
            "status": "PENDING",
            "customer_id": str(created["customer"].id),
            "braider_id": str(created["braider"]["braider_id"]),
            "booking_id": created["booking"]["id"],
            "currency": "EUR",
            "is_refunded": "false",
            "booking_date_from": created["starts_at"].date().isoformat(),
            "booking_date_to": created["starts_at"].date().isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total_items"] == 1
    item = data["items"][0]
    assert item["booking_id"] == created["booking"]["id"]
    assert item["booking_reference"] == created["booking"]["reference"]
    assert item["customer_email"] == "customer@example.com"
    assert item["braider_name"] == "Royal Braids"
    assert item["amount"] == created["booking"]["total"]
    assert item["stripe_payment_intent_id"].startswith("pi_test_")


async def test_admin_endpoints_require_admin_role(client: AsyncClient, db_session: AsyncSession):
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {customer_token}"}

    bookings_resp = await client.get(ADMIN_BOOKINGS_URL, headers=headers)
    payments_resp = await client.get(ADMIN_PAYMENTS_URL, headers=headers)

    assert bookings_resp.status_code == 403
    assert payments_resp.status_code == 403
