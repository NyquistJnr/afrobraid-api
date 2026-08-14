import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.modules.bookings.enums import BookingStatus
from app.modules.bookings.models import Booking
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"
BRAIDER_BOOKINGS_URL = "/api/v1/braiders/me/bookings"


async def _confirmed_booking(
    client: AsyncClient, db_session: AsyncSession, *, starts_at: datetime
) -> tuple[uuid.UUID, uuid.UUID]:
    braider = await create_bookable_braider(db_session, base_price="180.00", country="AT")
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    calc_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    calc = calc_resp.json()["data"]

    resp = await client.post(
        BOOKINGS_URL,
        json={
            "booking_calculation_id": calc["id"],
            "starts_at": (datetime.now(UTC) + timedelta(hours=10)).isoformat(),
            "terms_accepted": True,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    booking_id = uuid.UUID(resp.json()["data"]["id"])

    booking = await db_session.get(Booking, booking_id)
    booking.status = BookingStatus.CONFIRMED
    booking.confirmed_at = datetime.now(UTC)
    booking.starts_at = starts_at
    booking.ends_at = starts_at + timedelta(hours=4)
    await db_session.commit()

    return booking_id, braider["user"].id


async def test_braider_marks_no_show_after_appointment_time(
    client: AsyncClient, db_session: AsyncSession
):
    booking_id, braider_user_id = await _confirmed_booking(
        client, db_session, starts_at=datetime.now(UTC) - timedelta(hours=1)
    )
    token, _ = create_access_token(user_id=braider_user_id, user_type=UserType.BRAIDER.value)

    resp = await client.post(
        f"{BRAIDER_BOOKINGS_URL}/{booking_id}/no-show", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "NO_SHOW"

    booking = await db_session.get(Booking, booking_id)
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.NO_SHOW


async def test_braider_cannot_mark_no_show_before_appointment_time(
    client: AsyncClient, db_session: AsyncSession
):
    booking_id, braider_user_id = await _confirmed_booking(
        client, db_session, starts_at=datetime.now(UTC) + timedelta(hours=1)
    )
    token, _ = create_access_token(user_id=braider_user_id, user_type=UserType.BRAIDER.value)

    resp = await client.post(
        f"{BRAIDER_BOOKINGS_URL}/{booking_id}/no-show", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BOOKING_NO_SHOW_NOT_ALLOWED"


async def test_no_show_not_owner_returns_404(client: AsyncClient, db_session: AsyncSession):
    booking_id, _ = await _confirmed_booking(
        client, db_session, starts_at=datetime.now(UTC) - timedelta(hours=1)
    )
    other_braider = await create_bookable_braider(db_session, base_price="100.00", country="DE")
    token, _ = create_access_token(user_id=other_braider["user"].id, user_type=UserType.BRAIDER.value)

    resp = await client.post(
        f"{BRAIDER_BOOKINGS_URL}/{booking_id}/no-show", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


async def test_no_show_eligible_for_payout(client: AsyncClient, db_session: AsyncSession, fake_queue):
    """NO_SHOW should be picked up by release_due_payouts_cron the same as
    COMPLETED - confirms Phase 5's payout eligibility query already
    covers it (no change needed there)."""
    from sqlalchemy import select

    from app.modules.bookings import cron as bookings_cron
    from app.modules.bookings.models import BookingPayment
    from app.modules.bookings.tasks import TASK_RELEASE_BOOKING_PAYOUT

    booking_id, braider_user_id = await _confirmed_booking(
        client, db_session, starts_at=datetime.now(UTC) - timedelta(hours=54)
    )
    token, _ = create_access_token(user_id=braider_user_id, user_type=UserType.BRAIDER.value)

    payment_result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == booking_id)
    )
    from app.modules.bookings.enums import PaymentStatus

    payment = payment_result.scalars().one()
    payment.status = PaymentStatus.SUCCEEDED
    payment.stripe_charge_id = f"ch_test_{uuid.uuid4().hex[:16]}"
    await db_session.commit()

    resp = await client.post(
        f"{BRAIDER_BOOKINGS_URL}/{booking_id}/no-show", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text

    await bookings_cron.release_due_payouts_cron({"redis": fake_queue})
    job_kwargs = fake_queue.last_job_kwargs(TASK_RELEASE_BOOKING_PAYOUT)
    assert job_kwargs["booking_id"] == str(booking_id)
