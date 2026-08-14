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
DAC7_URL = "/api/v1/admin/dac7/report"


async def _completed_booking_in_quarter(
    client: AsyncClient, db_session: AsyncSession, *, ends_at: datetime
) -> dict:
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
    payment_result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == booking_id)
    )
    payment = payment_result.scalars().one()
    payment.status = PaymentStatus.SUCCEEDED
    booking.status = BookingStatus.COMPLETED
    booking.starts_at = ends_at - timedelta(hours=4)
    booking.ends_at = ends_at
    await db_session.commit()

    return {"booking_id": booking_id, "braider_id": braider["braider_id"], "booking": booking}


async def test_dac7_report_aggregates_completed_bookings_in_quarter(
    client: AsyncClient, db_session: AsyncSession
):
    ctx = await _completed_booking_in_quarter(
        client, db_session, ends_at=datetime(2026, 2, 15, 12, 0, tzinfo=UTC)
    )
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)

    resp = await client.get(
        DAC7_URL,
        params={"year": 2026, "quarter": 1},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["year"] == 2026
    assert data["quarter"] == 1

    row = next(r for r in data["rows"] if r["braider_id"] == str(ctx["braider_id"]))
    assert row["booking_count"] == 1
    assert row["country"] == "AT"
    assert row["tax_identification_number"] is None
    from decimal import Decimal

    assert Decimal(row["gross_consideration"]) == ctx["booking"].braider_share_total


async def test_dac7_report_excludes_bookings_outside_quarter(
    client: AsyncClient, db_session: AsyncSession
):
    ctx = await _completed_booking_in_quarter(
        client, db_session, ends_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    )
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)

    resp = await client.get(
        DAC7_URL,
        params={"year": 2026, "quarter": 1},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert all(r["braider_id"] != str(ctx["braider_id"]) for r in data["rows"])


async def test_dac7_report_rejects_invalid_quarter(client: AsyncClient, db_session: AsyncSession):
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    resp = await client.get(
        DAC7_URL,
        params={"year": 2026, "quarter": 5},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422  # FastAPI query validation (le=4)


async def test_dac7_report_requires_admin(client: AsyncClient, db_session: AsyncSession):
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    resp = await client.get(
        DAC7_URL,
        params={"year": 2026, "quarter": 1},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 403
