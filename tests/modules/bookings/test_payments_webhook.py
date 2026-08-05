import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.enums import BookingStatus, PaymentStatus
from app.modules.bookings.models import Booking, BookingPayment
from app.modules.bookings.payments import webhook as payments_webhook
from app.modules.bookings.tasks import TASK_SEND_BOOKING_CONFIRMED_EMAIL
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"
WEBHOOK_URL = "/api/v1/webhooks/stripe/payments"


class _FakeIntent:
    def __init__(self, intent_id: str, metadata: dict | None = None):
        self.id = intent_id
        self.metadata = metadata or {}
        self.latest_charge = f"ch_test_{uuid.uuid4().hex[:16]}"
        self.payment_method = f"pm_test_{uuid.uuid4().hex[:16]}"
        self.last_payment_error = None


class _FakeEvent:
    def __init__(self, event_id: str, event_type: str, data_object):
        self.id = event_id
        self.type = event_type
        self.data = type("Data", (), {"object": data_object})()


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
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    booking_id = resp.json()["data"]["id"]

    result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == uuid.UUID(booking_id))
    )
    payment = result.scalars().one()
    return booking_id, payment.stripe_payment_intent_id


async def test_webhook_confirms_booking_on_payment_succeeded(
    client: AsyncClient, db_session: AsyncSession, monkeypatch, fake_queue
):
    booking_id, pi_id = await _create_pending_booking(client, db_session)

    fake_event = _FakeEvent(
        f"evt_test_{uuid.uuid4().hex[:16]}",
        "payment_intent.succeeded",
        _FakeIntent(pi_id, metadata={"booking_id": booking_id, "purpose": "FULL"}),
    )

    def fake_construct(payload, sig_header):
        return fake_event

    monkeypatch.setattr(payments_webhook, "construct_payments_webhook_event", fake_construct)

    resp = await client.post(
        WEBHOOK_URL, json={}, headers={"Stripe-Signature": "t=1,v1=fake"}
    )
    assert resp.status_code == 200, resp.text

    booking = await db_session.get(Booking, uuid.UUID(booking_id))
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.CONFIRMED
    assert booking.confirmed_at is not None

    result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == booking.id)
    )
    payment = result.scalars().one()
    assert payment.status == PaymentStatus.SUCCEEDED

    fake_queue.last_job_kwargs(TASK_SEND_BOOKING_CONFIRMED_EMAIL)  # raises if not enqueued


async def test_webhook_duplicate_delivery_is_noop(
    client: AsyncClient, db_session: AsyncSession, monkeypatch, fake_queue
):
    booking_id, pi_id = await _create_pending_booking(client, db_session)

    event_id = f"evt_test_{uuid.uuid4().hex[:16]}"

    def fake_construct(payload, sig_header):
        return _FakeEvent(
            event_id,
            "payment_intent.succeeded",
            _FakeIntent(pi_id, metadata={"booking_id": booking_id, "purpose": "FULL"}),
        )

    monkeypatch.setattr(payments_webhook, "construct_payments_webhook_event", fake_construct)

    resp1 = await client.post(WEBHOOK_URL, json={}, headers={"Stripe-Signature": "t=1,v1=fake"})
    assert resp1.status_code == 200, resp1.text
    resp2 = await client.post(WEBHOOK_URL, json={}, headers={"Stripe-Signature": "t=1,v1=fake"})
    assert resp2.status_code == 200, resp2.text

    # Only one confirmation email despite two deliveries of the same event id.
    confirmed_jobs = [j for name, j in fake_queue.jobs if name == TASK_SEND_BOOKING_CONFIRMED_EMAIL]
    assert len(confirmed_jobs) == 1


async def test_webhook_rejects_invalid_signature(client: AsyncClient, monkeypatch):
    from app.modules.bookings.payments.client import StripeWebhookSignatureError

    def fake_construct(payload, sig_header):
        raise StripeWebhookSignatureError("bad signature")

    monkeypatch.setattr(payments_webhook, "construct_payments_webhook_event", fake_construct)

    resp = await client.post(WEBHOOK_URL, json={}, headers={"Stripe-Signature": "bad"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "STRIPE_INVALID_WEBHOOK_SIGNATURE"


async def test_webhook_marks_payment_failed(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    booking_id, pi_id = await _create_pending_booking(client, db_session)

    intent = _FakeIntent(pi_id, metadata={"booking_id": booking_id, "purpose": "FULL"})
    intent.last_payment_error = type("Err", (), {"code": "card_declined", "message": "Your card was declined."})()
    fake_event = _FakeEvent(f"evt_test_{uuid.uuid4().hex[:16]}", "payment_intent.payment_failed", intent)

    def fake_construct(payload, sig_header):
        return fake_event

    monkeypatch.setattr(payments_webhook, "construct_payments_webhook_event", fake_construct)

    resp = await client.post(WEBHOOK_URL, json={}, headers={"Stripe-Signature": "t=1,v1=fake"})
    assert resp.status_code == 200, resp.text

    result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == uuid.UUID(booking_id))
    )
    payment = result.scalars().one()
    assert payment.status == PaymentStatus.FAILED
    assert payment.failure_code == "card_declined"

    booking = await db_session.get(Booking, uuid.UUID(booking_id))
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.PENDING_PAYMENT
