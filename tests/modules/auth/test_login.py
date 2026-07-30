import pytest
from httpx import AsyncClient

from tests.modules.auth.helpers import SIGNUP_URL, signup_and_verify

pytestmark = pytest.mark.asyncio

LOGIN_URL = "/api/v1/auth/login"
EMAIL = "ada@example.com"
PASSWORD = "Password123"


async def test_login_before_verification_blocked(client: AsyncClient):
    await client.post(
        SIGNUP_URL,
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": EMAIL,
            "password": PASSWORD,
            "user_type": "CUSTOMER",
        },
    )

    resp = await client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


async def test_login_success(client: AsyncClient, fake_queue):
    await signup_and_verify(client, fake_queue, email=EMAIL, password=PASSWORD)

    resp = await client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == EMAIL
    assert body["user_type"] == "CUSTOMER"
    assert "access_token" in body
    assert "refresh_token" in body


async def test_login_wrong_password(client: AsyncClient, fake_queue):
    await signup_and_verify(client, fake_queue, email=EMAIL, password=PASSWORD)

    resp = await client.post(LOGIN_URL, json={"email": EMAIL, "password": "WrongPassword1"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_unknown_email(client: AsyncClient):
    resp = await client.post(LOGIN_URL, json={"email": "nobody@example.com", "password": PASSWORD})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"
