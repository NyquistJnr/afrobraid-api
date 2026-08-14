import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings import cron as bookings_cron
from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.enums import BookingStatus, PaymentStatus, TransferStatus
from app.modules.bookings.models import Booking, BookingPayment, BookingTransfer
from app.modules.bookings.payments import client as payments_client
from app.modules.bookings.payments import service as payments_service
from app.modules.bookings.tasks import (
    TASK_RELEASE_BOOKING_PAYOUT,
    TASK_SEND_DISPUTE_ADMIN_ALERT,
    TASK_SEND_PAYOUT_RELEASED_NOTIFICATION,
    release_booking_payout_task,
    send_dispute_admin_alert_task,
)
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"


async def _completed_booking(
    client: AsyncClient, db_session: AsyncSession, *, ends_at_ago: timedelta
) -> uuid.UUID:
    """Books, fast-forwards through CONFIRMED webhook confirmation, then
    directly sets status COMPLETED with an ends_at in the past - the state
    every payout test starts from."""
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
    booking_id = uuid.UUID(resp.json()["data"]["id"])

    booking = await db_session.get(Booking, booking_id)
    payment_result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == booking_id)
    )
    payment = payment_result.scalars().one()
    payment.status = PaymentStatus.SUCCEEDED
    payment.stripe_charge_id = f"ch_test_{uuid.uuid4().hex[:16]}"
    booking.status = BookingStatus.COMPLETED
    # ck_bookings_amounts requires ends_at > starts_at - move both into the
    # past together rather than just ends_at.
    booking.ends_at = datetime.now(UTC) - ends_at_ago
    booking.starts_at = booking.ends_at - timedelta(hours=4)
    await db_session.commit()

    return booking_id


async def test_start_due_bookings_cron_flips_confirmed_to_in_progress(
    client: AsyncClient, db_session: AsyncSession
):
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
    booking_id = uuid.UUID(resp.json()["data"]["id"])
    booking = await db_session.get(Booking, booking_id)
    booking.status = BookingStatus.CONFIRMED
    booking.starts_at = datetime.now(UTC) - timedelta(minutes=5)
    await db_session.commit()

    await bookings_cron.start_due_bookings_cron({})

    await db_session.refresh(booking)
    assert booking.status == BookingStatus.IN_PROGRESS


async def test_complete_due_bookings_cron_flips_in_progress_to_completed(
    client: AsyncClient, db_session: AsyncSession
):
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
    booking_id = uuid.UUID(resp.json()["data"]["id"])
    booking = await db_session.get(Booking, booking_id)
    booking.status = BookingStatus.IN_PROGRESS
    booking.ends_at = datetime.now(UTC) - timedelta(minutes=5)
    booking.starts_at = booking.ends_at - timedelta(hours=4)
    await db_session.commit()

    await bookings_cron.complete_due_bookings_cron({})

    await db_session.refresh(booking)
    assert booking.status == BookingStatus.COMPLETED


async def test_release_due_payouts_cron_enqueues_past_delay(
    client: AsyncClient, db_session: AsyncSession, fake_queue
):
    booking_id = await _completed_booking(client, db_session, ends_at_ago=timedelta(hours=49))

    await bookings_cron.release_due_payouts_cron({"redis": fake_queue})

    job_kwargs = fake_queue.last_job_kwargs(TASK_RELEASE_BOOKING_PAYOUT)
    assert job_kwargs["booking_id"] == str(booking_id)


async def test_release_due_payouts_cron_ignores_within_delay(
    client: AsyncClient, db_session: AsyncSession, fake_queue
):
    await _completed_booking(client, db_session, ends_at_ago=timedelta(hours=1))

    await bookings_cron.release_due_payouts_cron({"redis": fake_queue})

    assert fake_queue.jobs == []


async def test_release_booking_payout_task_transfers_braider_share(
    client: AsyncClient, db_session: AsyncSession, fake_queue
):
    booking_id = await _completed_booking(client, db_session, ends_at_ago=timedelta(hours=49))

    await release_booking_payout_task({"redis": fake_queue}, booking_id=str(booking_id))

    result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == booking_id)
    )
    payment = result.scalars().one()
    assert payment.amount_transferred_minor == payment.braider_share_minor

    transfer_result = await db_session.execute(
        select(BookingTransfer).where(BookingTransfer.booking_id == booking_id)
    )
    transfer = transfer_result.scalars().one()
    assert transfer.status == TransferStatus.SUCCEEDED

    fake_queue.last_job_kwargs(TASK_SEND_PAYOUT_RELEASED_NOTIFICATION)


async def test_release_booking_payout_task_noop_when_frozen(
    client: AsyncClient, db_session: AsyncSession, fake_queue, monkeypatch
):
    booking_id = await _completed_booking(client, db_session, ends_at_ago=timedelta(hours=49))
    booking = await db_session.get(Booking, booking_id)
    booking.payouts_frozen = True
    await db_session.commit()

    async def fail_if_called(**kwargs):
        raise AssertionError("Stripe should not be called for a frozen payout")

    monkeypatch.setattr(payments_client, "create_transfer", fail_if_called)

    await release_booking_payout_task({"redis": fake_queue}, booking_id=str(booking_id))

    result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == booking_id)
    )
    payment = result.scalars().one()
    assert payment.amount_transferred_minor == 0
    assert fake_queue.jobs == []


class _FakeDispute:
    def __init__(self, dispute_id: str, charge_id: str):
        self.id = dispute_id
        self.charge = charge_id


class _FakeEvent:
    def __init__(self, event_id: str, event_type: str, data_object):
        self.id = event_id
        self.type = event_type
        self.data = type("Data", (), {"object": data_object})()


async def test_dispute_webhook_freezes_payout_and_reverses_transfer(
    client: AsyncClient, db_session: AsyncSession, fake_queue
):
    booking_id = await _completed_booking(client, db_session, ends_at_ago=timedelta(hours=49))
    await release_booking_payout_task({"redis": fake_queue}, booking_id=str(booking_id))

    payment_result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == booking_id)
    )
    payment = payment_result.scalars().one()

    dispute = _FakeDispute(f"dp_test_{uuid.uuid4().hex[:16]}", payment.stripe_charge_id)
    event = _FakeEvent(f"evt_test_{uuid.uuid4().hex[:16]}", "charge.dispute.created", dispute)

    # payments_client.reverse_transfer already short-circuits to a
    # deterministic fake in the test environment - no monkeypatching needed.
    await payments_service.handle_webhook_event(
        db_session, fake_queue, event=event, source=payments_service.WebhookEventSource.PAYMENTS
    )

    booking = await db_session.get(Booking, booking_id)
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.DISPUTED
    assert booking.payouts_frozen is True
    assert booking.stripe_dispute_id == dispute.id

    transfer_result = await db_session.execute(
        select(BookingTransfer).where(BookingTransfer.booking_id == booking_id)
    )
    transfer = transfer_result.scalars().one()
    assert transfer.status == TransferStatus.REVERSED

    fake_queue.last_job_kwargs(TASK_SEND_DISPUTE_ADMIN_ALERT)


async def test_send_dispute_admin_alert_task_emails_admins(
    client: AsyncClient, db_session: AsyncSession, fake_queue
):
    booking_id = await _completed_booking(client, db_session, ends_at_ago=timedelta(hours=49))
    await create_user_with_token(db_session, user_type=UserType.ADMIN)

    await send_dispute_admin_alert_task(
        {"redis": fake_queue}, booking_id=str(booking_id), dispute_id="dp_test_123"
    )
    # No assertion error means the admin lookup + email + notification pipeline ran clean.
