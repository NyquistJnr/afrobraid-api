import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.enums import BookingStatus, PaymentStatus, WebhookEventSource, WebhookEventStatus
from app.modules.bookings.models import Booking, BookingPayment
from app.modules.bookings.payments import client as payments_client
from app.modules.bookings.payments import repository as payments_repo
from app.modules.bookings.payments import service as payments_service
from app.modules.bookings.payments.models import StripeWebhookEvent
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"


async def _pending_booking(client: AsyncClient, db_session: AsyncSession) -> tuple[str, str, dict]:
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

    payment_result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == uuid.UUID(booking_id))
    )
    payment = payment_result.scalars().one()
    return booking_id, str(payment.id), headers


def _fake_intent(*, status: str, pi_id: str, booking_id: str, purpose: str = "FULL"):
    return SimpleNamespace(
        id=pi_id,
        status=status,
        metadata={"booking_id": booking_id, "purpose": purpose},
        payment_method=f"pm_test_{uuid.uuid4().hex[:16]}",
        latest_charge=f"ch_test_{uuid.uuid4().hex[:16]}",
        last_payment_error=None,
    )


async def test_reconcile_pending_payment_confirms_on_succeeded(
    client: AsyncClient, db_session: AsyncSession, fake_queue, monkeypatch
):
    booking_id, payment_id, _ = await _pending_booking(client, db_session)
    payment = await bookings_repo.get_payment_by_id(db_session, uuid.UUID(payment_id))

    async def fake_retrieve(pi_id):
        return _fake_intent(status="succeeded", pi_id=pi_id, booking_id=booking_id)

    monkeypatch.setattr(payments_client, "retrieve_payment_intent", fake_retrieve)

    await payments_service.reconcile_pending_payment(db_session, fake_queue, payment)

    booking = await db_session.get(Booking, uuid.UUID(booking_id))
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.CONFIRMED

    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.SUCCEEDED


async def test_reconcile_pending_payment_fails_on_canceled(
    client: AsyncClient, db_session: AsyncSession, fake_queue, monkeypatch
):
    booking_id, payment_id, _ = await _pending_booking(client, db_session)
    payment = await bookings_repo.get_payment_by_id(db_session, uuid.UUID(payment_id))

    async def fake_retrieve(pi_id):
        return _fake_intent(status="canceled", pi_id=pi_id, booking_id=booking_id)

    monkeypatch.setattr(payments_client, "retrieve_payment_intent", fake_retrieve)

    await payments_service.reconcile_pending_payment(db_session, fake_queue, payment)

    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.FAILED

    booking = await db_session.get(Booking, uuid.UUID(booking_id))
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.PENDING_PAYMENT


async def test_reconcile_pending_payment_leaves_in_flight_alone(
    client: AsyncClient, db_session: AsyncSession, fake_queue, monkeypatch
):
    booking_id, payment_id, _ = await _pending_booking(client, db_session)
    payment = await bookings_repo.get_payment_by_id(db_session, uuid.UUID(payment_id))

    async def fake_retrieve(pi_id):
        return _fake_intent(status="requires_action", pi_id=pi_id, booking_id=booking_id)

    monkeypatch.setattr(payments_client, "retrieve_payment_intent", fake_retrieve)

    await payments_service.reconcile_pending_payment(db_session, fake_queue, payment)

    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.PENDING


async def test_list_stale_pending_payments_respects_age_threshold(
    client: AsyncClient, db_session: AsyncSession
):
    booking_id, payment_id, _ = await _pending_booking(client, db_session)
    payment = await bookings_repo.get_payment_by_id(db_session, uuid.UUID(payment_id))

    fresh = await bookings_repo.list_stale_pending_payments(
        db_session, older_than=datetime.now(UTC) - timedelta(hours=1), limit=100
    )
    assert payment.id not in [p.id for p in fresh]

    stale = await bookings_repo.list_stale_pending_payments(
        db_session, older_than=datetime.now(UTC) + timedelta(hours=1), limit=100
    )
    assert payment.id in [p.id for p in stale]


async def test_reprocess_webhook_event_replays_success(
    client: AsyncClient, db_session: AsyncSession, fake_queue, monkeypatch
):
    booking_id, payment_id, _ = await _pending_booking(client, db_session)
    payment = await bookings_repo.get_payment_by_id(db_session, uuid.UUID(payment_id))

    webhook_row = await payments_repo.create_received(
        db_session,
        stripe_event_id=f"evt_test_{uuid.uuid4().hex[:16]}",
        source=WebhookEventSource.PAYMENTS,
        event_type="payment_intent.succeeded",
        payload="{}",
    )
    await db_session.commit()

    fake_event = SimpleNamespace(
        id=webhook_row.stripe_event_id,
        type="payment_intent.succeeded",
        data=SimpleNamespace(
            object=_fake_intent(
                status="succeeded", pi_id=payment.stripe_payment_intent_id, booking_id=booking_id
            )
        ),
    )

    async def fake_retrieve_event(event_id):
        return fake_event

    monkeypatch.setattr(payments_client, "retrieve_payments_event", fake_retrieve_event)

    await payments_service.reprocess_webhook_event(db_session, fake_queue, webhook_row)

    await db_session.refresh(webhook_row)
    assert webhook_row.status == WebhookEventStatus.PROCESSED
    assert webhook_row.attempts == 2  # 1 from create_received, +1 from the retry

    booking = await db_session.get(Booking, uuid.UUID(booking_id))
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.CONFIRMED


async def test_list_stuck_events_finds_failed_and_stale_received(db_session: AsyncSession):
    failed_event = await payments_repo.create_received(
        db_session,
        stripe_event_id=f"evt_test_{uuid.uuid4().hex[:16]}",
        source=WebhookEventSource.PAYMENTS,
        event_type="payment_intent.succeeded",
        payload="{}",
    )
    await payments_repo.mark_failed(db_session, failed_event, error="boom")
    await db_session.commit()

    stuck = await payments_repo.list_stuck_events(
        db_session, stuck_since=datetime.now(UTC) + timedelta(hours=1), max_attempts=5, limit=100
    )
    assert failed_event.stripe_event_id in [e.stripe_event_id for e in stuck]

    exhausted = await payments_repo.list_stuck_events(
        db_session, stuck_since=datetime.now(UTC) + timedelta(hours=1), max_attempts=0, limit=100
    )
    assert failed_event.stripe_event_id not in [e.stripe_event_id for e in exhausted]


async def test_admin_retry_webhook_event_endpoint(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    booking_id, payment_id, _ = await _pending_booking(client, db_session)
    payment = await bookings_repo.get_payment_by_id(db_session, uuid.UUID(payment_id))

    webhook_row = await payments_repo.create_received(
        db_session,
        stripe_event_id=f"evt_test_{uuid.uuid4().hex[:16]}",
        source=WebhookEventSource.PAYMENTS,
        event_type="payment_intent.succeeded",
        payload="{}",
    )
    await db_session.commit()

    fake_event = SimpleNamespace(
        id=webhook_row.stripe_event_id,
        type="payment_intent.succeeded",
        data=SimpleNamespace(
            object=_fake_intent(
                status="succeeded", pi_id=payment.stripe_payment_intent_id, booking_id=booking_id
            )
        ),
    )

    async def fake_retrieve_event(event_id):
        return fake_event

    monkeypatch.setattr(payments_client, "retrieve_payments_event", fake_retrieve_event)

    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    resp = await client.post(
        f"/api/v1/admin/payments/webhook-events/{webhook_row.stripe_event_id}/retry",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "PROCESSED"


async def test_admin_retry_webhook_event_not_found(client: AsyncClient, db_session: AsyncSession):
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    resp = await client.post(
        "/api/v1/admin/payments/webhook-events/evt_does_not_exist/retry",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "WEBHOOK_EVENT_NOT_FOUND"


async def test_admin_reconcile_booking_endpoint(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    booking_id, payment_id, _ = await _pending_booking(client, db_session)

    async def fake_retrieve(pi_id):
        return _fake_intent(status="succeeded", pi_id=pi_id, booking_id=booking_id)

    monkeypatch.setattr(payments_client, "retrieve_payment_intent", fake_retrieve)

    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    resp = await client.post(
        f"/api/v1/admin/payments/bookings/{booking_id}/reconcile",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["payments_checked"] == 1

    booking = await db_session.get(Booking, uuid.UUID(booking_id))
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.CONFIRMED
