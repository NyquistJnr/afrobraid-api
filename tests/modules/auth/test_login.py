import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_token
from app.modules.auth.repository import get_refresh_token_by_hash
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


async def test_login_remember_me_extends_refresh_token_ttl(
    client: AsyncClient, fake_queue, db_session: AsyncSession
):
    settings = get_settings()

    await signup_and_verify(client, fake_queue, email=EMAIL, password=PASSWORD)

    normal_resp = await client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})
    remember_resp = await client.post(
        LOGIN_URL, json={"email": EMAIL, "password": PASSWORD, "remember_me": True}
    )

    normal_token = await get_refresh_token_by_hash(
        db_session, hash_token(normal_resp.json()["refresh_token"])
    )
    remember_token = await get_refresh_token_by_hash(
        db_session, hash_token(remember_resp.json()["refresh_token"])
    )

    normal_lifetime = normal_token.expires_at - normal_token.created_at
    remember_lifetime = remember_token.expires_at - remember_token.created_at

    assert remember_lifetime > normal_lifetime
    assert remember_lifetime.days >= settings.remember_me_refresh_token_expire_days - 1
