import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.enums import BalanceChargeState, BookingStatus, PaymentStatus, TransferStatus
from app.modules.bookings.models import Booking, BookingPayment, BookingTransfer, CancelledBy
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"
BRAIDER_BOOKINGS_URL = "/api/v1/braiders/me/bookings"


async def _confirmed_booking(
    client: AsyncClient, db_session: AsyncSession, *, starts_at_offset: timedelta
) -> dict:
    """Books at the given offset and simulates the first payment's webhook
    confirmation directly against the DB, landing CONFIRMED - same
    shortcut test_balance_charge.py uses to avoid mocking Stripe for the
    part of the flow this test isn't exercising."""
    braider = await create_bookable_braider(db_session, base_price="180.00", country="AT")
    customer, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {customer_token}"}

    calc_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    calc = calc_resp.json()["data"]
    starts_at = datetime.now(UTC) + starts_at_offset

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
    booking.status = BookingStatus.CONFIRMED
    booking.confirmed_at = datetime.now(UTC)
    await db_session.commit()

    return {
        "booking_id": booking_id,
        "customer_headers": headers,
        "braider_user_id": braider["user"].id,
    }


async def _braider_headers_for(db_session: AsyncSession, braider_user_id: uuid.UUID) -> dict:
    from app.core.security import create_access_token

    token, _ = create_access_token(user_id=braider_user_id, user_type=UserType.BRAIDER.value)
    return {"Authorization": f"Bearer {token}"}


async def test_customer_cancel_before_cutoff_forfeits_deposit_and_releases_share(
    client: AsyncClient, db_session: AsyncSession, fake_queue
):
    ctx = await _confirmed_booking(client, db_session, starts_at_offset=timedelta(days=10))

    resp = await client.post(
        f"{BOOKINGS_URL}/{ctx['booking_id']}/cancel", headers=ctx["customer_headers"]
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "CANCELLED_BY_CUSTOMER"
    assert data["cancelled_by"] == "CUSTOMER"

    booking = await db_session.get(Booking, ctx["booking_id"])
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.CANCELLED_BY_CUSTOMER
    assert booking.cancelled_by == CancelledBy.CUSTOMER
    assert booking.balance_charge_state == BalanceChargeState.ABANDONED

    result = await db_session.execute(
        select(BookingTransfer).where(BookingTransfer.booking_id == ctx["booking_id"])
    )
    transfer = result.scalars().one()
    assert transfer.status == TransferStatus.SUCCEEDED
    assert transfer.stripe_transfer_id is not None


async def test_customer_cancel_inside_cutoff_rejected(client: AsyncClient, db_session: AsyncSession):
    ctx = await _confirmed_booking(client, db_session, starts_at_offset=timedelta(hours=10))

    resp = await client.post(
        f"{BOOKINGS_URL}/{ctx['booking_id']}/cancel", headers=ctx["customer_headers"]
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BOOKING_CANCELLATION_WINDOW_CLOSED"


async def test_customer_cancel_not_owner_returns_404(client: AsyncClient, db_session: AsyncSession):
    ctx = await _confirmed_booking(client, db_session, starts_at_offset=timedelta(days=10))
    _, other_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)

    resp = await client.post(
        f"{BOOKINGS_URL}/{ctx['booking_id']}/cancel",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404


async def test_customer_cancel_twice_second_call_rejected(
    client: AsyncClient, db_session: AsyncSession
):
    ctx = await _confirmed_booking(client, db_session, starts_at_offset=timedelta(days=10))

    resp1 = await client.post(
        f"{BOOKINGS_URL}/{ctx['booking_id']}/cancel", headers=ctx["customer_headers"]
    )
    assert resp1.status_code == 200

    resp2 = await client.post(
        f"{BOOKINGS_URL}/{ctx['booking_id']}/cancel", headers=ctx["customer_headers"]
    )
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "BOOKING_NOT_CANCELLABLE"


async def test_braider_cancel_fully_refunds_customer(
    client: AsyncClient, db_session: AsyncSession
):
    ctx = await _confirmed_booking(client, db_session, starts_at_offset=timedelta(days=10))
    braider_headers = await _braider_headers_for(db_session, ctx["braider_user_id"])

    resp = await client.post(
        f"{BRAIDER_BOOKINGS_URL}/{ctx['booking_id']}/cancel",
        json={"reason": "Family emergency, can't make the appointment."},
        headers=braider_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "CANCELLED_BY_BRAIDER"
    assert data["cancellation_reason"] == "Family emergency, can't make the appointment."

    booking = await db_session.get(Booking, ctx["booking_id"])
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.CANCELLED_BY_BRAIDER
    assert booking.cancelled_by == CancelledBy.BRAIDER

    result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == ctx["booking_id"])
    )
    payment = result.scalars().one()
    assert payment.amount_refunded_minor == payment.amount_minor


async def test_braider_cancel_requires_nonblank_reason(
    client: AsyncClient, db_session: AsyncSession
):
    ctx = await _confirmed_booking(client, db_session, starts_at_offset=timedelta(days=10))
    braider_headers = await _braider_headers_for(db_session, ctx["braider_user_id"])

    resp = await client.post(
        f"{BRAIDER_BOOKINGS_URL}/{ctx['booking_id']}/cancel",
        json={"reason": "   "},
        headers=braider_headers,
    )
    assert resp.status_code == 422


async def test_braider_cancel_not_owner_returns_404(client: AsyncClient, db_session: AsyncSession):
    ctx = await _confirmed_booking(client, db_session, starts_at_offset=timedelta(days=10))
    other_braider = await create_bookable_braider(db_session, base_price="100.00", country="DE")
    other_headers = await _braider_headers_for(db_session, other_braider["user"].id)

    resp = await client.post(
        f"{BRAIDER_BOOKINGS_URL}/{ctx['booking_id']}/cancel",
        json={"reason": "not my booking"},
        headers=other_headers,
    )
    assert resp.status_code == 404


async def test_braider_cancel_allowed_inside_24h(client: AsyncClient, db_session: AsyncSession):
    """No cutoff for a braider cancel, unlike the customer path."""
    ctx = await _confirmed_booking(client, db_session, starts_at_offset=timedelta(hours=10))
    braider_headers = await _braider_headers_for(db_session, ctx["braider_user_id"])

    resp = await client.post(
        f"{BRAIDER_BOOKINGS_URL}/{ctx['booking_id']}/cancel",
        json={"reason": "Illness"},
        headers=braider_headers,
    )
    assert resp.status_code == 200, resp.text
