import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.modules.bookings.enums import BookingStatus
from app.modules.bookings.models import Booking
from app.modules.users.models import UserType
from app.shared import links
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"
CHAT_URL = "/api/v1/chat"
NOTIFICATIONS_URL = "/api/v1/notifications"


def _braider_headers(braider: dict) -> dict:
    token, _ = create_access_token(
        user_id=braider["user"].id, user_type=braider["user"].user_type.value
    )
    return {"Authorization": f"Bearer {token}"}


async def _send_chat_message_to_braider(
    client: AsyncClient, db_session: AsyncSession, *, body: str = "Hi there"
) -> dict:
    """Sets up a confirmed booking + thread and sends one customer -> braider
    message, which is currently the only thing that creates a Notification -
    returns headers/ids the caller needs."""
    braider = await create_bookable_braider(db_session)
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    braider_headers = _braider_headers(braider)

    calc_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    calc = calc_resp.json()["data"]
    book_resp = await client.post(
        BOOKINGS_URL,
        json={
            "booking_calculation_id": calc["id"],
            "starts_at": (datetime.now(UTC) + timedelta(hours=10)).isoformat(),
            "terms_accepted": True,
        },
        headers=customer_headers,
    )
    booking_id = uuid.UUID(book_resp.json()["data"]["id"])
    booking = await db_session.get(Booking, booking_id)
    booking.status = BookingStatus.CONFIRMED
    booking.confirmed_at = datetime.now(UTC)
    await db_session.commit()

    thread_id = (
        await client.get(f"{CHAT_URL}/bookings/{booking_id}/thread", headers=customer_headers)
    ).json()["data"]["id"]
    send_resp = await client.post(
        f"{CHAT_URL}/threads/{thread_id}/messages", json={"body": body}, headers=customer_headers
    )
    assert send_resp.status_code == 200, send_resp.text

    return {
        "braider": braider,
        "braider_headers": braider_headers,
        "customer_headers": customer_headers,
        "thread_id": thread_id,
    }


async def test_recipient_gets_notification_for_new_chat_message(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(links.settings, "braider_frontend_url", "https://braiders.example.com")
    ctx = await _send_chat_message_to_braider(client, db_session, body="Hi, see you soon!")

    resp = await client.get(NOTIFICATIONS_URL, headers=ctx["braider_headers"])
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert len(items) == 1
    notification = items[0]
    assert notification["type"] == "CHAT_NEW_MESSAGE"
    assert notification["is_read"] is False
    assert notification["related_type"] == "chat_thread"
    assert notification["related_id"] == ctx["thread_id"]
    assert "sent you a message" in notification["body"]
    assert f"https://braiders.example.com/en/chat/{ctx['thread_id']}" in notification["body"]

    # The customer (sender) doesn't get their own notification.
    sender_resp = await client.get(NOTIFICATIONS_URL, headers=ctx["customer_headers"])
    assert sender_resp.json()["data"]["items"] == []


async def test_notification_localizes_via_lang_query_param(client: AsyncClient, db_session: AsyncSession):
    ctx = await _send_chat_message_to_braider(client, db_session)

    resp = await client.get(f"{NOTIFICATIONS_URL}?lang=fr", headers=ctx["braider_headers"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["items"][0]["title"] == "Nouveau message"


async def test_mark_read_then_mark_all_read(client: AsyncClient, db_session: AsyncSession):
    ctx = await _send_chat_message_to_braider(client, db_session)

    list_resp = await client.get(NOTIFICATIONS_URL, headers=ctx["braider_headers"])
    notification_id = list_resp.json()["data"]["items"][0]["id"]

    read_resp = await client.patch(
        f"{NOTIFICATIONS_URL}/{notification_id}/read", headers=ctx["braider_headers"]
    )
    assert read_resp.status_code == 200, read_resp.text
    assert read_resp.json()["data"]["is_read"] is True
    assert read_resp.json()["data"]["read_at"] is not None

    # A second message on the same thread so read-all has something unread
    # to sweep up (a fresh call to the helper would spin up an unrelated
    # braider/thread instead of adding to this one).
    await client.post(
        f"{CHAT_URL}/threads/{ctx['thread_id']}/messages",
        json={"body": "one more thing"},
        headers=ctx["customer_headers"],
    )

    unread_before = await client.get(f"{NOTIFICATIONS_URL}?is_read=false", headers=ctx["braider_headers"])
    assert len(unread_before.json()["data"]["items"]) == 1

    read_all_resp = await client.post(f"{NOTIFICATIONS_URL}/read-all", headers=ctx["braider_headers"])
    assert read_all_resp.status_code == 200, read_all_resp.text
    assert read_all_resp.json()["data"]["marked_count"] == 1

    unread_after = await client.get(f"{NOTIFICATIONS_URL}?is_read=false", headers=ctx["braider_headers"])
    assert unread_after.json()["data"]["items"] == []


async def test_delete_notification(client: AsyncClient, db_session: AsyncSession):
    ctx = await _send_chat_message_to_braider(client, db_session)
    list_resp = await client.get(NOTIFICATIONS_URL, headers=ctx["braider_headers"])
    notification_id = list_resp.json()["data"]["items"][0]["id"]

    delete_resp = await client.delete(f"{NOTIFICATIONS_URL}/{notification_id}", headers=ctx["braider_headers"])
    assert delete_resp.status_code == 200, delete_resp.text

    after_resp = await client.get(NOTIFICATIONS_URL, headers=ctx["braider_headers"])
    assert after_resp.json()["data"]["items"] == []

    missing_resp = await client.delete(f"{NOTIFICATIONS_URL}/{notification_id}", headers=ctx["braider_headers"])
    assert missing_resp.status_code == 404
    assert missing_resp.json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"


async def test_pagination(client: AsyncClient, db_session: AsyncSession):
    ctx = await _send_chat_message_to_braider(client, db_session, body="first")
    for i in range(3):
        await client.post(
            f"{CHAT_URL}/threads/{ctx['thread_id']}/messages",
            json={"body": f"message {i}"},
            headers=ctx["customer_headers"],
        )

    page1 = await client.get(f"{NOTIFICATIONS_URL}?page=1&page_size=2", headers=ctx["braider_headers"])
    assert page1.status_code == 200, page1.text
    body = page1.json()["data"]
    assert len(body["items"]) == 2
    assert body["pagination"]["total_items"] == 4
    assert body["pagination"]["total_pages"] == 2
    assert body["pagination"]["has_next"] is True

    page2 = await client.get(f"{NOTIFICATIONS_URL}?page=2&page_size=2", headers=ctx["braider_headers"])
    assert len(page2.json()["data"]["items"]) == 2
    assert page2.json()["data"]["pagination"]["has_next"] is False


async def test_date_range_filter(client: AsyncClient, db_session: AsyncSession):
    ctx = await _send_chat_message_to_braider(client, db_session)

    # `params=` (rather than hand-building the query string) lets httpx
    # percent-encode the "+" UTC offset in these ISO timestamps - a literal
    # "+" in a raw query string decodes server-side as a space.
    far_future = (datetime.now(UTC) + timedelta(days=365)).isoformat()
    empty_resp = await client.get(
        NOTIFICATIONS_URL, params={"date_from": far_future}, headers=ctx["braider_headers"]
    )
    assert empty_resp.status_code == 200, empty_resp.text
    assert empty_resp.json()["data"]["items"] == []

    far_past = (datetime.now(UTC) - timedelta(days=365)).isoformat()
    present_resp = await client.get(
        NOTIFICATIONS_URL, params={"date_from": far_past}, headers=ctx["braider_headers"]
    )
    assert len(present_resp.json()["data"]["items"]) == 1

    invalid_resp = await client.get(
        NOTIFICATIONS_URL,
        params={"date_from": far_future, "date_to": far_past},
        headers=ctx["braider_headers"],
    )
    assert invalid_resp.status_code == 400
    assert invalid_resp.json()["error"]["code"] == "INVALID_DATE_RANGE"
