import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import UserType
from tests.helpers import create_user_with_token

pytestmark = pytest.mark.asyncio

PROFILE_URL = "/api/v1/users/me"


@pytest.mark.parametrize("user_type", [UserType.CUSTOMER, UserType.BRAIDER, UserType.ADMIN])
async def test_get_profile_returns_current_user(
    client: AsyncClient, db_session: AsyncSession, user_type: UserType
):
    user, token = await create_user_with_token(db_session, user_type=user_type)
    resp = await client.get(PROFILE_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["id"] == str(user.id)
    assert data["email"] == user.email
    assert data["user_type"] == user_type.value


async def test_get_profile_requires_auth(client: AsyncClient):
    resp = await client.get(PROFILE_URL)
    assert resp.status_code == 401


@pytest.mark.parametrize("user_type", [UserType.CUSTOMER, UserType.BRAIDER, UserType.ADMIN])
async def test_patch_profile_updates_provided_fields_only(
    client: AsyncClient, db_session: AsyncSession, user_type: UserType
):
    user, token = await create_user_with_token(db_session, user_type=user_type)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.patch(
        PROFILE_URL, json={"first_name": "Amaka"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["first_name"] == "Amaka"
    assert data["last_name"] == user.last_name
    assert data["email"] == user.email


async def test_patch_profile_updates_phone_number(client: AsyncClient, db_session: AsyncSession):
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.patch(
        PROFILE_URL, json={"phone_number": "+15551234567"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["phone_number"] == "+15551234567"


async def test_patch_profile_rejects_phone_number_already_in_use(
    client: AsyncClient, db_session: AsyncSession
):
    other, _ = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    other.phone_number = "+15551234567"
    await db_session.commit()

    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.patch(
        PROFILE_URL, json={"phone_number": "+15551234567"}, headers=headers
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PHONE_ALREADY_EXISTS"


async def test_patch_profile_can_clear_last_name(client: AsyncClient, db_session: AsyncSession):
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.patch(PROFILE_URL, json={"last_name": None}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["last_name"] is None


async def test_patch_profile_rejects_blank_first_name(
    client: AsyncClient, db_session: AsyncSession
):
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.patch(PROFILE_URL, json={"first_name": "  "}, headers=headers)
    assert resp.status_code == 422
