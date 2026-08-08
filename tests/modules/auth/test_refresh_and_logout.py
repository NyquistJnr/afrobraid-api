import pytest
from httpx import AsyncClient

from tests.modules.auth.helpers import signup_and_verify

pytestmark = pytest.mark.asyncio

REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
EMAIL = "ada@example.com"
PASSWORD = "Password123"


async def test_refresh_rotates_token(client: AsyncClient, fake_queue):
    tokens = await signup_and_verify(client, fake_queue, email=EMAIL, password=PASSWORD)
    old_refresh = tokens["refresh_token"]

    resp = await client.post(REFRESH_URL, json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    new_tokens = resp.json()["data"]
    assert new_tokens["refresh_token"] != old_refresh
    assert new_tokens["access_token"] != tokens["access_token"]

    reuse_resp = await client.post(REFRESH_URL, json={"refresh_token": old_refresh})
    assert reuse_resp.status_code == 401
    assert reuse_resp.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    second_use_resp = await client.post(
        REFRESH_URL, json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert second_use_resp.status_code == 200


async def test_refresh_invalid_token(client: AsyncClient):
    resp = await client.post(REFRESH_URL, json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


async def test_logout_revokes_refresh_token(client: AsyncClient, fake_queue):
    tokens = await signup_and_verify(client, fake_queue, email=EMAIL, password=PASSWORD)
    refresh_token = tokens["refresh_token"]

    logout_resp = await client.post(LOGOUT_URL, json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 200

    refresh_resp = await client.post(REFRESH_URL, json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401
    assert refresh_resp.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"
