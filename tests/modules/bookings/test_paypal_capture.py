import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.enums import BookingStatus, PaymentStatus
from app.modules.bookings.models import Booking, BookingPayment
from app.modules.bookings.tasks import (
    TASK_SEND_BOOKING_CONFIRMED_EMAIL,
    TASK_SEND_PAYMENT_NOTIFICATION,
    TASK_SEND_PAYMENT_RECEIPT_EMAIL,
)
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"


async def _create_pending_paypal_booking(client: AsyncClient, db_session: AsyncSession) -> tuple[str, dict]:
    braider = await create_bookable_braider(db_session, base_price="180.00", country="AT")
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

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
    return resp.json()["data"]["id"], headers


async def test_capture_confirms_booking(client: AsyncClient, db_session: AsyncSession, fake_queue):
    booking_id, headers = await _create_pending_paypal_booking(client, db_session)

    resp = await client.post(f"{BOOKINGS_URL}/{booking_id}/payments/paypal/capture", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "CONFIRMED"

    booking = await db_session.get(Booking, uuid.UUID(booking_id))
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.CONFIRMED
    assert booking.confirmed_at is not None

    result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == booking.id)
    )
    payment = result.scalars().one()
    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.paypal_capture_id is not None
    assert payment.paypal_capture_id.startswith("paypal_capture_test_")

    fake_queue.last_job_kwargs(TASK_SEND_BOOKING_CONFIRMED_EMAIL)
    fake_queue.last_job_kwargs(TASK_SEND_PAYMENT_RECEIPT_EMAIL)
    fake_queue.last_job_kwargs(TASK_SEND_PAYMENT_NOTIFICATION)


async def test_capture_is_idempotent(client: AsyncClient, db_session: AsyncSession, fake_queue):
    booking_id, headers = await _create_pending_paypal_booking(client, db_session)

    resp1 = await client.post(f"{BOOKINGS_URL}/{booking_id}/payments/paypal/capture", headers=headers)
    assert resp1.status_code == 200, resp1.text
    resp2 = await client.post(f"{BOOKINGS_URL}/{booking_id}/payments/paypal/capture", headers=headers)
    assert resp2.status_code == 200, resp2.text

    confirmed_jobs = [j for name, j in fake_queue.jobs if name == TASK_SEND_BOOKING_CONFIRMED_EMAIL]
    assert len(confirmed_jobs) == 1


async def test_capture_rejects_other_customer(client: AsyncClient, db_session: AsyncSession):
    booking_id, _ = await _create_pending_paypal_booking(client, db_session)
    _, other_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)

    resp = await client.post(
        f"{BOOKINGS_URL}/{booking_id}/payments/paypal/capture",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404


async def test_capture_rejects_stripe_booking(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session, base_price="180.00", country="AT")
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

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
    booking_id = resp.json()["data"]["id"]

    capture_resp = await client.post(f"{BOOKINGS_URL}/{booking_id}/payments/paypal/capture", headers=headers)
    assert capture_resp.status_code == 409
    assert capture_resp.json()["error"]["code"] == "BOOKING_PAYMENT_NOT_CAPTURABLE"
