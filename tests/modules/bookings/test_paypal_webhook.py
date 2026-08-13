import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.enums import BookingStatus, PaymentStatus
from app.modules.bookings.models import Booking, BookingPayment
from app.modules.bookings.payments import paypal_webhook
from app.modules.bookings.tasks import TASK_SEND_BOOKING_CONFIRMED_EMAIL
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"
WEBHOOK_URL = "/api/v1/webhooks/paypal/payments"


def _capture_event(event_id: str, *, order_id: str, capture_id: str, booking_id: str, status: str = "COMPLETED"):
    return {
        "id": event_id,
        "event_type": "PAYMENT.CAPTURE.COMPLETED" if status == "COMPLETED" else "PAYMENT.CAPTURE.DENIED",
        "resource": {
            "id": capture_id,
            "status": status,
            "custom_id": f"{booking_id}:FULL",
            "supplementary_data": {"related_ids": {"order_id": order_id}},
        },
    }


async def _create_pending_booking(client: AsyncClient, db_session: AsyncSession) -> tuple[str, str]:
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
    booking_id = resp.json()["data"]["id"]

    result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == uuid.UUID(booking_id))
    )
    payment = result.scalars().one()
    return booking_id, payment.paypal_order_id


async def test_webhook_confirms_booking_on_capture_completed(
    client: AsyncClient, db_session: AsyncSession, monkeypatch, fake_queue
):
    booking_id, order_id = await _create_pending_booking(client, db_session)
    event = _capture_event(
        f"evt_paypal_test_{uuid.uuid4().hex[:16]}",
        order_id=order_id,
        capture_id=f"paypal_capture_test_{uuid.uuid4().hex[:16]}",
        booking_id=booking_id,
    )

    async def fake_construct(headers, raw_body):
        return event

    monkeypatch.setattr(paypal_webhook, "construct_webhook_event", fake_construct)

    resp = await client.post(WEBHOOK_URL, json={})
    assert resp.status_code == 200, resp.text

    booking = await db_session.get(Booking, uuid.UUID(booking_id))
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.CONFIRMED

    result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == booking.id)
    )
    payment = result.scalars().one()
    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.paypal_capture_id == event["resource"]["id"]

    fake_queue.last_job_kwargs(TASK_SEND_BOOKING_CONFIRMED_EMAIL)


async def test_webhook_duplicate_delivery_is_noop(
    client: AsyncClient, db_session: AsyncSession, monkeypatch, fake_queue
):
    booking_id, order_id = await _create_pending_booking(client, db_session)
    event = _capture_event(
        f"evt_paypal_test_{uuid.uuid4().hex[:16]}",
        order_id=order_id,
        capture_id=f"paypal_capture_test_{uuid.uuid4().hex[:16]}",
        booking_id=booking_id,
    )

    async def fake_construct(headers, raw_body):
        return event

    monkeypatch.setattr(paypal_webhook, "construct_webhook_event", fake_construct)

    resp1 = await client.post(WEBHOOK_URL, json={})
    assert resp1.status_code == 200, resp1.text
    resp2 = await client.post(WEBHOOK_URL, json={})
    assert resp2.status_code == 200, resp2.text

    confirmed_jobs = [j for name, j in fake_queue.jobs if name == TASK_SEND_BOOKING_CONFIRMED_EMAIL]
    assert len(confirmed_jobs) == 1


async def test_webhook_is_noop_when_already_captured_via_endpoint(
    client: AsyncClient, db_session: AsyncSession, monkeypatch, fake_queue
):
    booking_id, order_id = await _create_pending_booking(client, db_session)
    result = await db_session.execute(select(Booking).where(Booking.id == uuid.UUID(booking_id)))
    booking = result.scalars().one()

    # Simulate the capture endpoint already having finalized this payment -
    # the webhook here is a reconciliation safety net, not the primary path.
    from app.modules.bookings.payments import service as payments_service

    result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == booking.id)
    )
    payment = result.scalars().one()
    await payments_service.finalize_payment_succeeded(
        db_session,
        fake_queue,
        payment,
        provider_order_id=order_id,
        provider_charge_id="paypal_capture_already_done",
    )
    assert len(fake_queue.jobs) > 0
    jobs_before = len(fake_queue.jobs)

    event = _capture_event(
        f"evt_paypal_test_{uuid.uuid4().hex[:16]}",
        order_id=order_id,
        capture_id="paypal_capture_from_webhook",
        booking_id=booking_id,
    )

    async def fake_construct(headers, raw_body):
        return event

    monkeypatch.setattr(paypal_webhook, "construct_webhook_event", fake_construct)

    resp = await client.post(WEBHOOK_URL, json={})
    assert resp.status_code == 200, resp.text

    # No new confirmation/receipt/notification jobs from the redundant webhook.
    assert len(fake_queue.jobs) == jobs_before


async def test_webhook_marks_payment_failed_on_capture_denied(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    booking_id, order_id = await _create_pending_booking(client, db_session)
    event = _capture_event(
        f"evt_paypal_test_{uuid.uuid4().hex[:16]}",
        order_id=order_id,
        capture_id=f"paypal_capture_test_{uuid.uuid4().hex[:16]}",
        booking_id=booking_id,
        status="DENIED",
    )

    async def fake_construct(headers, raw_body):
        return event

    monkeypatch.setattr(paypal_webhook, "construct_webhook_event", fake_construct)

    resp = await client.post(WEBHOOK_URL, json={})
    assert resp.status_code == 200, resp.text

    result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == uuid.UUID(booking_id))
    )
    payment = result.scalars().one()
    assert payment.status == PaymentStatus.FAILED

    booking = await db_session.get(Booking, uuid.UUID(booking_id))
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.PENDING_PAYMENT


async def test_webhook_ignores_unhandled_event_type(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    booking_id, order_id = await _create_pending_booking(client, db_session)
    event = {
        "id": f"evt_paypal_test_{uuid.uuid4().hex[:16]}",
        "event_type": "CHECKOUT.ORDER.APPROVED",
        "resource": {"id": order_id, "custom_id": f"{booking_id}:FULL"},
    }

    async def fake_construct(headers, raw_body):
        return event

    monkeypatch.setattr(paypal_webhook, "construct_webhook_event", fake_construct)

    resp = await client.post(WEBHOOK_URL, json={})
    assert resp.status_code == 200, resp.text

    result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == uuid.UUID(booking_id))
    )
    payment = result.scalars().one()
    assert payment.status == PaymentStatus.PENDING


async def test_webhook_rejects_invalid_signature(client: AsyncClient, monkeypatch):
    from app.modules.bookings.payments.paypal_client import PaypalWebhookSignatureError

    async def fake_construct(headers, raw_body):
        raise PaypalWebhookSignatureError("bad signature")

    monkeypatch.setattr(paypal_webhook, "construct_webhook_event", fake_construct)

    resp = await client.post(WEBHOOK_URL, json={})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "PAYPAL_INVALID_WEBHOOK_SIGNATURE"
