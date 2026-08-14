import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.enums import BalanceChargeState, ReceiptType
from app.modules.bookings.models import Booking, BookingPayment
from app.modules.bookings.payments import webhook as payments_webhook
from app.modules.bookings.receipts.models import Receipt
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"
RECEIPTS_URL = "/api/v1/receipts"


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


async def _confirm_via_webhook(
    client: AsyncClient, monkeypatch, booking_id: str, pi_id: str, purpose: str
) -> None:
    fake_event = _FakeEvent(
        f"evt_test_{uuid.uuid4().hex[:16]}",
        "payment_intent.succeeded",
        _FakeIntent(pi_id, metadata={"booking_id": booking_id, "purpose": purpose}),
    )

    def fake_construct(payload, sig_header):
        return fake_event

    monkeypatch.setattr(payments_webhook, "construct_payments_webhook_event", fake_construct)

    resp = await client.post(
        "/api/v1/webhooks/stripe/payments", json={}, headers={"Stripe-Signature": "t=1,v1=fake"}
    )
    assert resp.status_code == 200, resp.text


async def test_full_upfront_booking_issues_invoice_receipt(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
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
    assert resp.status_code == 201, resp.text
    booking_id = resp.json()["data"]["id"]

    payment_result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == uuid.UUID(booking_id))
    )
    payment = payment_result.scalars().one()

    await _confirm_via_webhook(client, monkeypatch, booking_id, payment.stripe_payment_intent_id, "FULL")

    receipt_result = await db_session.execute(
        select(Receipt).where(Receipt.booking_id == uuid.UUID(booking_id))
    )
    receipt = receipt_result.scalars().one()
    assert receipt.type == ReceiptType.INVOICE
    assert receipt.receipt_number.startswith(f"{datetime.now(UTC).year}-")
    assert receipt.prior_receipts_total == 0

    view_resp = await client.get(f"{RECEIPTS_URL}/{receipt.public_token}")
    assert view_resp.status_code == 200
    assert receipt.receipt_number in view_resp.text
    assert "Invoice" in view_resp.text


async def test_receipt_not_found_for_bad_token(client: AsyncClient):
    resp = await client.get(f"{RECEIPTS_URL}/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RECEIPT_NOT_FOUND"


async def test_balance_receipt_deducts_prior_deposit_receipt(
    client: AsyncClient, db_session: AsyncSession, fake_queue, monkeypatch
):
    from app.modules.bookings.tasks import charge_booking_balance_task

    braider = await create_bookable_braider(db_session, base_price="180.00", country="AT")
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    calc_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    calc = calc_resp.json()["data"]
    starts_at = datetime.now(UTC) + timedelta(days=60)

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
    deposit_payment = payment_result.scalars().one()

    await _confirm_via_webhook(client, monkeypatch, booking_id, deposit_payment.stripe_payment_intent_id, "DEPOSIT")

    deposit_receipt_result = await db_session.execute(
        select(Receipt).where(Receipt.booking_id == uuid.UUID(booking_id))
    )
    deposit_receipt = deposit_receipt_result.scalars().one()

    booking = await db_session.get(Booking, uuid.UUID(booking_id))
    booking.balance_charge_due_at = datetime.now(UTC) - timedelta(minutes=5)
    booking.balance_charge_state = BalanceChargeState.DUE
    await db_session.commit()

    await charge_booking_balance_task({"redis": fake_queue}, booking_id=booking_id)

    receipts_result = await db_session.execute(
        select(Receipt).where(Receipt.booking_id == uuid.UUID(booking_id)).order_by(Receipt.issued_at)
    )
    receipts = list(receipts_result.scalars().all())
    assert len(receipts) == 2
    balance_receipt = receipts[1]
    assert balance_receipt.prior_receipts_total == deposit_receipt.amount_total


async def test_list_booking_receipts_endpoint(client: AsyncClient, db_session: AsyncSession, monkeypatch):
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
    booking_id = resp.json()["data"]["id"]

    payment_result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == uuid.UUID(booking_id))
    )
    payment = payment_result.scalars().one()
    await _confirm_via_webhook(client, monkeypatch, booking_id, payment.stripe_payment_intent_id, "FULL")

    list_resp = await client.get(f"{BOOKINGS_URL}/{booking_id}/receipts", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    data = list_resp.json()["data"]
    assert len(data) == 1
    assert data[0]["type"] == "INVOICE"
    assert data[0]["url"].endswith(f"/api/v1/receipts/{data[0]['url'].rsplit('/', 1)[-1]}")


async def test_braider_cancel_issues_credit_note(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    from app.core.security import create_access_token

    braider = await create_bookable_braider(db_session, base_price="180.00", country="AT")
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    calc_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    calc = calc_resp.json()["data"]
    starts_at = datetime.now(UTC) + timedelta(days=10)

    resp = await client.post(
        BOOKINGS_URL,
        json={
            "booking_calculation_id": calc["id"],
            "starts_at": starts_at.isoformat(),
            "terms_accepted": True,
        },
        headers=headers,
    )
    booking_id = resp.json()["data"]["id"]

    payment_result = await db_session.execute(
        select(BookingPayment).where(BookingPayment.booking_id == uuid.UUID(booking_id))
    )
    payment = payment_result.scalars().one()
    await _confirm_via_webhook(client, monkeypatch, booking_id, payment.stripe_payment_intent_id, "FULL")

    invoice_result = await db_session.execute(
        select(Receipt).where(Receipt.booking_id == uuid.UUID(booking_id))
    )
    invoice_receipt = invoice_result.scalars().one()

    braider_token, _ = create_access_token(user_id=braider["user"].id, user_type=UserType.BRAIDER.value)
    cancel_resp = await client.post(
        f"/api/v1/braiders/me/bookings/{booking_id}/cancel",
        json={"reason": "Unavailable"},
        headers={"Authorization": f"Bearer {braider_token}"},
    )
    assert cancel_resp.status_code == 200, cancel_resp.text

    receipts_result = await db_session.execute(
        select(Receipt).where(Receipt.booking_id == uuid.UUID(booking_id)).order_by(Receipt.issued_at)
    )
    receipts = list(receipts_result.scalars().all())
    assert len(receipts) == 2
    credit_note = receipts[1]
    assert credit_note.type == ReceiptType.CREDIT_NOTE
    assert credit_note.credit_note_for_receipt_id == invoice_receipt.id
