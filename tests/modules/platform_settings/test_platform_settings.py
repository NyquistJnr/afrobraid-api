import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import UserType
from tests.helpers import create_user_with_token

pytestmark = pytest.mark.asyncio

SETTINGS_URL = "/api/v1/admin/platform-settings"


async def _admin_headers(db_session: AsyncSession) -> dict:
    _, token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    return {"Authorization": f"Bearer {token}"}


async def test_get_settings_returns_seeded_defaults(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(db_session)

    resp = await client.get(SETTINGS_URL, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["platform_fee_type"] == "PERCENTAGE"
    assert data["platform_fee_value"] == "10.00"
    assert data["vat_type"] == "PERCENTAGE"
    assert data["vat_value"] == "20.00"

    # Fetching again returns the same (already-created) row, not a new one.
    second_resp = await client.get(SETTINGS_URL, headers=headers)
    assert second_resp.json()["data"]["id"] == data["id"]


async def test_patch_updates_only_given_fields(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(db_session)

    resp = await client.patch(SETTINGS_URL, json={"platform_fee_value": "12.50"}, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["platform_fee_type"] == "PERCENTAGE"
    assert data["platform_fee_value"] == "12.50"
    # VAT untouched.
    assert data["vat_type"] == "PERCENTAGE"
    assert data["vat_value"] == "20.00"


async def test_patch_can_switch_to_fixed_amount(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(db_session)

    resp = await client.patch(
        SETTINGS_URL,
        json={"platform_fee_type": "FIXED", "platform_fee_value": "5.00"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["platform_fee_type"] == "FIXED"
    assert data["platform_fee_value"] == "5.00"


async def test_patch_rejects_percentage_over_100(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(db_session)

    resp = await client.patch(SETTINGS_URL, json={"vat_value": "150.00"}, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SETTING_VALUE"

    # Switching to FIXED with the same value is fine - the 100 cap is
    # percentage-only.
    resp = await client.patch(
        SETTINGS_URL, json={"vat_type": "FIXED", "vat_value": "150.00"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["vat_value"] == "150.00"


async def test_patch_rejects_negative_value(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(db_session)

    resp = await client.patch(SETTINGS_URL, json={"platform_fee_value": "-1.00"}, headers=headers)
    assert resp.status_code == 422


async def test_non_admin_cannot_access_platform_settings(
    client: AsyncClient, db_session: AsyncSession
):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(SETTINGS_URL, headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    resp = await client.patch(SETTINGS_URL, json={"vat_value": "5.00"}, headers=headers)
    assert resp.status_code == 403


async def test_unauthenticated_cannot_access_platform_settings(client: AsyncClient):
    resp = await client.get(SETTINGS_URL)
    assert resp.status_code == 401
