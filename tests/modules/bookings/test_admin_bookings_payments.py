import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.enums import BookingStatus, PaymentStatus
from app.modules.bookings.models import Booking, BookingPayment
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"
ADMIN_BOOKINGS_URL = "/api/v1/admin/bookings"
ADMIN_BRAIDERS_URL = "/api/v1/admin/braiders"
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


async def test_admin_can_view_braider_customer_bookings_and_stats(
    client: AsyncClient, db_session: AsyncSession
):
    created = await _create_booking(client, db_session)
    booking = await db_session.get(Booking, uuid.UUID(created["booking"]["id"]))
    booking.status = BookingStatus.COMPLETED
    payment = (
        await db_session.execute(
            select(BookingPayment).where(BookingPayment.booking_id == booking.id)
        )
    ).scalars().one()
    payment.status = PaymentStatus.SUCCEEDED
    await db_session.commit()
    await db_session.refresh(booking)

    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    headers = {"Authorization": f"Bearer {admin_token}"}

    pair_resp = await client.get(
        f"{ADMIN_BOOKINGS_URL}/braiders/{created['braider']['braider_id']}"
        f"/customers/{created['customer'].id}",
        params={
            "status": "COMPLETED",
            "date_from": created["starts_at"].date().isoformat(),
            "date_to": created["starts_at"].date().isoformat(),
        },
        headers=headers,
    )
    assert pair_resp.status_code == 200, pair_resp.text
    pair_data = pair_resp.json()["data"]
    assert pair_data["total_items"] == 1
    assert pair_data["items"][0]["id"] == created["booking"]["id"]

    braider_stats_resp = await client.get(
        f"{ADMIN_BOOKINGS_URL}/braiders/{created['braider']['braider_id']}/stats",
        headers=headers,
    )
    assert braider_stats_resp.status_code == 200, braider_stats_resp.text
    braider_stats = braider_stats_resp.json()["data"]
    assert braider_stats["braider"]["id"] == str(created["braider"]["braider_id"])
    assert braider_stats["total_bookings"] == 1
    assert braider_stats["completed_bookings"] == 1
    assert braider_stats["unique_customers"] == 1
    assert braider_stats["total_amount_paid"] == created["booking"]["total"]
    assert braider_stats["total_amount_made_by_braider"] == str(booking.braider_share_total)

    customer_stats_resp = await client.get(
        f"{ADMIN_BOOKINGS_URL}/customers/{created['customer'].id}/stats",
        headers=headers,
    )
    assert customer_stats_resp.status_code == 200, customer_stats_resp.text
    customer_stats = customer_stats_resp.json()["data"]
    assert customer_stats["customer"]["id"] == str(created["customer"].id)
    assert customer_stats["unique_braiders"] == 1
    assert customer_stats["total_amount_spent_by_customer"] == created["booking"]["total"]


async def test_admin_can_view_braider_onboarding_and_charts(
    client: AsyncClient, db_session: AsyncSession
):
    created = await _create_booking(client, db_session)
    booking = await db_session.get(Booking, uuid.UUID(created["booking"]["id"]))
    booking.status = BookingStatus.COMPLETED
    payment = (
        await db_session.execute(
            select(BookingPayment).where(BookingPayment.booking_id == booking.id)
        )
    ).scalars().one()
    payment.status = PaymentStatus.SUCCEEDED
    await db_session.commit()

    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    headers = {"Authorization": f"Bearer {admin_token}"}

    onboarding_resp = await client.get(
        f"{ADMIN_BRAIDERS_URL}/{created['braider']['braider_id']}/onboarding",
        headers=headers,
    )
    assert onboarding_resp.status_code == 200, onboarding_resp.text
    onboarding = onboarding_resp.json()["data"]
    assert onboarding["braider_id"] == str(created["braider"]["braider_id"])
    assert len(onboarding["steps"]) == 8
    assert all(step["completed"] for step in onboarding["steps"])

    revenue_resp = await client.get(
        f"{ADMIN_BOOKINGS_URL}/braiders/{created['braider']['braider_id']}/charts/revenue",
        params={
            "date_from": created["starts_at"].date().isoformat(),
            "date_to": created["starts_at"].date().isoformat(),
        },
        headers=headers,
    )
    assert revenue_resp.status_code == 200, revenue_resp.text
    revenue = revenue_resp.json()["data"]
    assert revenue["metric"] == "braider_earnings"
    assert revenue["points"][0]["amount"] == str(booking.braider_share_total)

    weekday_resp = await client.get(
        f"{ADMIN_BOOKINGS_URL}/customers/{created['customer'].id}/charts/weekday",
        headers=headers,
    )
    assert weekday_resp.status_code == 200, weekday_resp.text
    weekday = weekday_resp.json()["data"]
    assert weekday["metric"] == "customer_spend_by_weekday"
    assert len(weekday["points"]) == 7
    assert sum(point["bookings_count"] for point in weekday["points"]) == 1

    style_resp = await client.get(
        f"{ADMIN_BOOKINGS_URL}/braiders/{created['braider']['braider_id']}"
        f"/customers/{created['customer'].id}/charts/styles",
        headers=headers,
    )
    assert style_resp.status_code == 200, style_resp.text
    style = style_resp.json()["data"]
    assert style["metric"] == "braider_earnings_by_style"
    assert style["slices"][0]["style_name"] == "Knotless Braids"


async def test_admin_endpoints_require_admin_role(client: AsyncClient, db_session: AsyncSession):
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {customer_token}"}

    bookings_resp = await client.get(ADMIN_BOOKINGS_URL, headers=headers)
    payments_resp = await client.get(ADMIN_PAYMENTS_URL, headers=headers)

    assert bookings_resp.status_code == 403
    assert payments_resp.status_code == 403
