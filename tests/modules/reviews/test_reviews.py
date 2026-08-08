import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.enums import BookingStatus
from app.modules.bookings.models import Booking
from app.modules.reviews.tasks import TASK_TRANSLATE_REVIEW_COMMENT
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"
BOOKINGS_URL = "/api/v1/bookings"


def _reviews_url(braider_id) -> str:
    return f"/api/v1/braiders/{braider_id}/reviews"


async def _create_confirmed_booking(
    client: AsyncClient, db_session: AsyncSession, *, braider: dict, customer_headers: dict
) -> None:
    """Full checkout flow (mirrors test_double_booking.py) then flips the
    resulting booking straight to CONFIRMED, standing in for a webhook-driven
    payment success - the only thing reviews.repository.has_eligible_booking
    actually checks."""
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
    await db_session.commit()


async def test_cannot_review_without_an_eligible_booking(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session)
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.put(
        f"{_reviews_url(braider['braider_id'])}/me",
        json={"rating": 5, "comment": "Amazing!"},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "REVIEW_NOT_ELIGIBLE"


async def test_rating_reflects_immediately_comment_needs_admin_approval(
    client: AsyncClient, db_session: AsyncSession, fake_queue
):
    braider = await create_bookable_braider(db_session)
    customer, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}
    await _create_confirmed_booking(client, db_session, braider=braider, customer_headers=headers)

    resp = await client.put(
        f"{_reviews_url(braider['braider_id'])}/me",
        json={"rating": 5, "comment": "Amazing braids, so gentle!"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["rating"] == 5
    assert data["status"] == "PENDING"
    assert data["comment_en"] == "Amazing braids, so gentle!"
    assert data["comment_en_source"] == "HUMAN"
    assert data["comment_de_source"] == "PENDING"
    assert data["comment_fr_source"] == "PENDING"

    job = fake_queue.last_job_kwargs(TASK_TRANSLATE_REVIEW_COMMENT)
    assert job["source_locale"] == "en"
    assert job["source_text"] == "Amazing braids, so gentle!"
    assert set(job["target_locales"]) == {"de", "fr"}

    # Rating shows up on discovery immediately, before any moderation.
    detail_resp = await client.get(f"/api/v1/braiders/{braider['braider_id']}")
    assert detail_resp.json()["data"]["rating"] == "5.00"

    search_resp = await client.get("/api/v1/braiders")
    search_item = next(
        i for i in search_resp.json()["data"]["items"] if i["id"] == str(braider["braider_id"])
    )
    assert search_item["rating"] == "5.00"

    # But the comment isn't public yet.
    public_resp = await client.get(_reviews_url(braider["braider_id"]))
    assert public_resp.json()["data"]["items"] == []


async def test_rating_only_review_with_no_comment_is_auto_approved(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(db_session)
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}
    await _create_confirmed_booking(client, db_session, braider=braider, customer_headers=headers)

    resp = await client.put(
        f"{_reviews_url(braider['braider_id'])}/me", json={"rating": 4}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "APPROVED"

    public_resp = await client.get(_reviews_url(braider["braider_id"]))
    items = public_resp.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["rating"] == 4
    assert items[0]["comment"] is None


async def test_customer_has_one_review_per_braider_and_can_update_it(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(db_session)
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}
    await _create_confirmed_booking(client, db_session, braider=braider, customer_headers=headers)

    first = await client.put(
        f"{_reviews_url(braider['braider_id'])}/me", json={"rating": 3}, headers=headers
    )
    assert first.status_code == 200, first.text
    review_id = first.json()["data"]["id"]

    second = await client.put(
        f"{_reviews_url(braider['braider_id'])}/me", json={"rating": 5}, headers=headers
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["id"] == review_id
    assert second.json()["data"]["rating"] == 5

    detail_resp = await client.get(f"/api/v1/braiders/{braider['braider_id']}")
    assert detail_resp.json()["data"]["rating"] == "5.00"

    me_resp = await client.get(f"{_reviews_url(braider['braider_id'])}/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["rating"] == 5


async def test_get_my_review_404s_when_none_exists(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session)
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(f"{_reviews_url(braider['braider_id'])}/me", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "REVIEW_NOT_FOUND"


async def test_admin_approve_makes_comment_public(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session)
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    await _create_confirmed_booking(client, db_session, braider=braider, customer_headers=customer_headers)

    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    review_resp = await client.put(
        f"{_reviews_url(braider['braider_id'])}/me",
        json={"rating": 5, "comment": "Loved it"},
        headers=customer_headers,
    )
    review_id = review_resp.json()["data"]["id"]

    pending_list = await client.get("/api/v1/admin/reviews", headers=admin_headers)
    assert pending_list.status_code == 200, pending_list.text
    assert any(r["id"] == review_id for r in pending_list.json()["data"]["items"])

    approve_resp = await client.post(
        f"/api/v1/admin/reviews/{review_id}/approve", headers=admin_headers
    )
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["data"]["status"] == "APPROVED"

    public_resp = await client.get(_reviews_url(braider["braider_id"]))
    items = public_resp.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["comment"] == "Loved it"


async def test_admin_reject_excludes_rating_from_average(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session)
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    await _create_confirmed_booking(client, db_session, braider=braider, customer_headers=customer_headers)

    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    review_resp = await client.put(
        f"{_reviews_url(braider['braider_id'])}/me", json={"rating": 1}, headers=customer_headers
    )
    review_id = review_resp.json()["data"]["id"]

    detail_before = await client.get(f"/api/v1/braiders/{braider['braider_id']}")
    assert detail_before.json()["data"]["rating"] == "1.00"

    reject_resp = await client.post(
        f"/api/v1/admin/reviews/{review_id}/reject", headers=admin_headers
    )
    assert reject_resp.status_code == 200, reject_resp.text
    assert reject_resp.json()["data"]["status"] == "REJECTED"

    detail_after = await client.get(f"/api/v1/braiders/{braider['braider_id']}")
    assert detail_after.json()["data"]["rating"] is None


async def test_editing_an_approved_comment_resets_it_to_pending(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(db_session)
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    await _create_confirmed_booking(client, db_session, braider=braider, customer_headers=customer_headers)

    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    review_resp = await client.put(
        f"{_reviews_url(braider['braider_id'])}/me",
        json={"rating": 5, "comment": "Great!"},
        headers=customer_headers,
    )
    review_id = review_resp.json()["data"]["id"]
    await client.post(f"/api/v1/admin/reviews/{review_id}/approve", headers=admin_headers)

    update_resp = await client.put(
        f"{_reviews_url(braider['braider_id'])}/me",
        json={"rating": 5, "comment": "Actually, even better than I thought!"},
        headers=customer_headers,
    )
    assert update_resp.json()["data"]["status"] == "PENDING"

    public_resp = await client.get(_reviews_url(braider["braider_id"]))
    assert public_resp.json()["data"]["items"] == []


async def test_scoped_to_own_role(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session)
    _, braider_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)

    resp = await client.put(
        f"{_reviews_url(braider['braider_id'])}/me",
        json={"rating": 5},
        headers={"Authorization": f"Bearer {braider_token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    admin_only_resp = await client.get(
        "/api/v1/admin/reviews", headers={"Authorization": f"Bearer {braider_token}"}
    )
    assert admin_only_resp.status_code == 403
