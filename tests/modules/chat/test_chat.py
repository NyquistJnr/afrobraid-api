import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.modules.bookings.enums import BookingStatus
from app.modules.bookings.models import Booking
from app.modules.chat import tasks as chat_tasks
from app.modules.chat.models import ChatMessage
from app.modules.chat.tasks import TASK_TRANSLATE_CHAT_MESSAGE
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"
CHAT_URL = "/api/v1/chat"


def _braider_headers(braider: dict) -> dict:
    token, _ = create_access_token(
        user_id=braider["user"].id, user_type=braider["user"].user_type.value
    )
    return {"Authorization": f"Bearer {token}"}


async def _create_confirmed_booking(
    client: AsyncClient, db_session: AsyncSession, *, braider: dict, customer_headers: dict
) -> uuid.UUID:
    """Full checkout flow, then flips the booking straight to CONFIRMED with
    confirmed_at set - standing in for a webhook-driven deposit/full payment
    success (see bookings.payments.service), the only thing
    chat.service.get_or_create_thread_for_booking checks."""
    calc_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    assert calc_resp.status_code == 201, calc_resp.text
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
    assert book_resp.status_code == 201, book_resp.text
    booking_id = uuid.UUID(book_resp.json()["data"]["id"])

    booking = await db_session.get(Booking, booking_id)
    booking.status = BookingStatus.CONFIRMED
    booking.confirmed_at = datetime.now(UTC)
    await db_session.commit()
    return booking_id


async def test_chat_unavailable_before_deposit_paid(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session)
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

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
        headers=headers,
    )
    booking_id = book_resp.json()["data"]["id"]

    resp = await client.get(f"{CHAT_URL}/bookings/{booking_id}/thread", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CHAT_NOT_AVAILABLE"


async def test_thread_lifecycle_send_list_unread_mark_read(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session)
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    braider_headers = _braider_headers(braider)

    booking_id = await _create_confirmed_booking(
        client, db_session, braider=braider, customer_headers=customer_headers
    )

    thread_resp = await client.get(f"{CHAT_URL}/bookings/{booking_id}/thread", headers=customer_headers)
    assert thread_resp.status_code == 200, thread_resp.text
    thread_id = thread_resp.json()["data"]["id"]
    assert thread_resp.json()["data"]["unread_count"] == 0

    # Braider opening the same booking's thread gets the same one back.
    braider_thread_resp = await client.get(f"{CHAT_URL}/bookings/{booking_id}/thread", headers=braider_headers)
    assert braider_thread_resp.json()["data"]["id"] == thread_id

    send_resp = await client.post(
        f"{CHAT_URL}/threads/{thread_id}/messages",
        json={"body": "Hi, looking forward to it!"},
        headers=customer_headers,
    )
    assert send_resp.status_code == 200, send_resp.text
    message = send_resp.json()["data"]
    assert message["status"] == "SENT"
    assert message["body"] == "Hi, looking forward to it!"
    assert message["violation_notice"] is None

    braider_threads = await client.get(f"{CHAT_URL}/threads", headers=braider_headers)
    item = next(t for t in braider_threads.json()["data"]["items"] if t["id"] == thread_id)
    assert item["unread_count"] == 1
    assert item["last_message_preview"] == "Hi, looking forward to it!"
    assert item["last_message_flagged"] is False

    messages_resp = await client.get(f"{CHAT_URL}/threads/{thread_id}/messages", headers=braider_headers)
    assert len(messages_resp.json()["data"]["items"]) == 1

    read_resp = await client.post(f"{CHAT_URL}/threads/{thread_id}/read", headers=braider_headers)
    assert read_resp.status_code == 200, read_resp.text
    assert read_resp.json()["data"]["unread_count"] == 0


async def test_message_with_contact_info_is_flagged_and_never_stored_in_plaintext(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(db_session)
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    booking_id = await _create_confirmed_booking(
        client, db_session, braider=braider, customer_headers=customer_headers
    )
    thread_id = (
        await client.get(f"{CHAT_URL}/bookings/{booking_id}/thread", headers=customer_headers)
    ).json()["data"]["id"]

    resp = await client.post(
        f"{CHAT_URL}/threads/{thread_id}/messages",
        json={"body": "call me at 555-123-4567"},
        headers=customer_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "FLAGGED"
    assert data["body"] is None
    assert data["violation_notice"]
    assert "555-123-4567" not in resp.text

    message = await db_session.get(ChatMessage, uuid.UUID(data["id"]))
    assert message.body is None
    assert message.body_hash is not None
    assert "phone_or_account_number" in (message.violation_types or "")

    # The inbox preview never leaks flagged content either.
    threads_resp = await client.get(f"{CHAT_URL}/threads", headers=customer_headers)
    item = next(t for t in threads_resp.json()["data"]["items"] if t["id"] == thread_id)
    assert item["last_message_preview"] is None
    assert item["last_message_flagged"] is True


async def test_translation_only_enqueued_once_both_sides_set_different_chat_locales(
    client: AsyncClient, db_session: AsyncSession, fake_queue
):
    braider = await create_bookable_braider(db_session)
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    braider_headers = _braider_headers(braider)
    booking_id = await _create_confirmed_booking(
        client, db_session, braider=braider, customer_headers=customer_headers
    )
    thread_id = (
        await client.get(f"{CHAT_URL}/bookings/{booking_id}/thread", headers=customer_headers)
    ).json()["data"]["id"]

    # Neither side has set a chat_locale yet - no translation.
    resp1 = await client.post(
        f"{CHAT_URL}/threads/{thread_id}/messages", json={"body": "Hello there"}, headers=customer_headers
    )
    assert resp1.json()["data"]["translated_body"] is None
    assert not [j for j in fake_queue.jobs if j[0] == TASK_TRANSLATE_CHAT_MESSAGE]

    profile_resp = await client.patch("/api/v1/users/me", json={"chat_locale": "en"}, headers=customer_headers)
    assert profile_resp.status_code == 200, profile_resp.text
    await client.patch("/api/v1/users/me", json={"chat_locale": "fr"}, headers=braider_headers)

    resp2 = await client.post(
        f"{CHAT_URL}/threads/{thread_id}/messages", json={"body": "Hello again"}, headers=customer_headers
    )
    assert resp2.status_code == 200, resp2.text
    # Translation is async - not filled in on the immediate response.
    assert resp2.json()["data"]["translated_body"] is None
    message_id = resp2.json()["data"]["id"]

    job = fake_queue.last_job_kwargs(TASK_TRANSLATE_CHAT_MESSAGE)
    assert job["message_id"] == message_id
    assert job["source_locale"] == "en"
    assert job["target_locale"] == "fr"

    await chat_tasks.translate_chat_message_task({}, **job)

    updated = await db_session.get(ChatMessage, uuid.UUID(message_id))
    await db_session.refresh(updated)
    assert updated.translation_status == "DONE"
    assert updated.translated_locale == "fr"
    assert updated.translated_body == "[fr] Hello again"


async def test_no_translation_when_both_sides_share_the_same_chat_locale(
    client: AsyncClient, db_session: AsyncSession, fake_queue
):
    braider = await create_bookable_braider(db_session)
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    braider_headers = _braider_headers(braider)
    booking_id = await _create_confirmed_booking(
        client, db_session, braider=braider, customer_headers=customer_headers
    )
    thread_id = (
        await client.get(f"{CHAT_URL}/bookings/{booking_id}/thread", headers=customer_headers)
    ).json()["data"]["id"]

    await client.patch("/api/v1/users/me", json={"chat_locale": "en"}, headers=customer_headers)
    await client.patch("/api/v1/users/me", json={"chat_locale": "en"}, headers=braider_headers)

    resp = await client.post(
        f"{CHAT_URL}/threads/{thread_id}/messages", json={"body": "Same language, no translation needed"},
        headers=customer_headers,
    )
    assert resp.json()["data"]["translated_body"] is None
    assert not [j for j in fake_queue.jobs if j[0] == TASK_TRANSLATE_CHAT_MESSAGE]


async def test_report_participant_and_admin_moderation(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session)
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    booking_id = await _create_confirmed_booking(
        client, db_session, braider=braider, customer_headers=customer_headers
    )
    thread_id = (
        await client.get(f"{CHAT_URL}/bookings/{booking_id}/thread", headers=customer_headers)
    ).json()["data"]["id"]

    report_resp = await client.post(
        f"{CHAT_URL}/threads/{thread_id}/report",
        json={"reason": "HARASSMENT", "details": "Was rude in chat"},
        headers=customer_headers,
    )
    assert report_resp.status_code == 200, report_resp.text
    report = report_resp.json()["data"]
    assert report["reported_user_id"] == str(braider["user"].id)
    assert report["status"] == "OPEN"

    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    list_resp = await client.get("/api/v1/admin/chat/reports", headers=admin_headers)
    assert list_resp.status_code == 200, list_resp.text
    assert any(r["id"] == report["id"] for r in list_resp.json()["data"]["items"])

    update_resp = await client.patch(
        f"/api/v1/admin/chat/reports/{report['id']}",
        json={"status": "RESOLVED", "admin_notes": "Warned the braider"},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["data"]["status"] == "RESOLVED"
    assert update_resp.json()["data"]["admin_notes"] == "Warned the braider"

    # No longer shows up in the default OPEN queue.
    open_list = await client.get("/api/v1/admin/chat/reports", headers=admin_headers)
    assert not any(r["id"] == report["id"] for r in open_list.json()["data"]["items"])


async def test_non_participant_cannot_access_thread(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session)
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    booking_id = await _create_confirmed_booking(
        client, db_session, braider=braider, customer_headers=customer_headers
    )
    thread_id = (
        await client.get(f"{CHAT_URL}/bookings/{booking_id}/thread", headers=customer_headers)
    ).json()["data"]["id"]

    _, other_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    resp = await client.get(f"{CHAT_URL}/threads/{thread_id}/messages", headers=other_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CHAT_ACCESS_DENIED"
