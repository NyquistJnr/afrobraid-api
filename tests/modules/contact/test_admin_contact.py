import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import UserType
from tests.helpers import create_user_with_token

pytestmark = pytest.mark.asyncio

CONTACT_URL = "/api/v1/contact"
ADMIN_CONTACT_URL = "/api/v1/admin/contact-submissions"


async def _submit_contact(
    client: AsyncClient,
    *,
    email: str,
    platform: str = "CUSTOMER",
    purpose: str = "GENERAL",
    subject: str = "Hello",
    message: str = "I need help with my booking.",
) -> str:
    resp = await client.post(
        CONTACT_URL,
        json={
            "first_name": "Ada",
            "last_name": "Nwosu",
            "phone_number": "+15551234567",
            "email": email,
            "subject": subject,
            "message": message,
            "platform": platform,
            "purpose": purpose,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def test_admin_can_list_filter_search_and_mark_contact_read(
    client: AsyncClient, db_session: AsyncSession
):
    first_id = await _submit_contact(
        client,
        email="ada@example.com",
        platform="CUSTOMER",
        purpose="PRICING",
        subject="Pricing question",
        message="Do you have discounts?",
    )
    await _submit_contact(
        client,
        email="braider@example.com",
        platform="BRAIDER",
        purpose="PARTNER",
        subject="Partner request",
        message="I want to partner with Afrobraid.",
    )

    admin, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    headers = {"Authorization": f"Bearer {admin_token}"}

    list_resp = await client.get(
        ADMIN_CONTACT_URL,
        params={"platform": "CUSTOMER", "purpose": "PRICING", "is_read": "false", "search": "discounts"},
        headers=headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    data = list_resp.json()["data"]
    assert data["pagination"]["total_items"] == 1
    item = data["items"][0]
    assert item["id"] == first_id
    assert item["is_read"] is False
    assert item["full_name"] == "Ada Nwosu"

    detail_resp = await client.get(f"{ADMIN_CONTACT_URL}/{first_id}", headers=headers)
    assert detail_resp.status_code == 200, detail_resp.text
    assert detail_resp.json()["data"]["email"] == "ada@example.com"

    read_resp = await client.post(f"{ADMIN_CONTACT_URL}/{first_id}/mark-read", headers=headers)
    assert read_resp.status_code == 200, read_resp.text
    read_data = read_resp.json()["data"]
    assert read_data["is_read"] is True
    assert read_data["read_at"] is not None
    assert read_data["read_by_admin_id"] == str(admin.id)

    unread_resp = await client.post(f"{ADMIN_CONTACT_URL}/{first_id}/mark-unread", headers=headers)
    assert unread_resp.status_code == 200, unread_resp.text
    unread_data = unread_resp.json()["data"]
    assert unread_data["is_read"] is False
    assert unread_data["read_at"] is None
    assert unread_data["read_by_admin_id"] is None


async def test_admin_contact_requires_admin_role(client: AsyncClient, db_session: AsyncSession):
    _, customer_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    resp = await client.get(
        ADMIN_CONTACT_URL, headers={"Authorization": f"Bearer {customer_token}"}
    )
    assert resp.status_code == 403
