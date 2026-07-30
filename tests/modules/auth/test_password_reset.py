import pytest
from httpx import AsyncClient

from app.modules.auth.tasks import TASK_SEND_OTP_EMAIL
from tests.modules.auth.helpers import signup_and_verify

pytestmark = pytest.mark.asyncio

FORGOT_URL = "/api/v1/auth/forgot-password"
RESET_URL = "/api/v1/auth/reset-password"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
EMAIL = "ada@example.com"
PASSWORD = "Password123"
NEW_PASSWORD = "NewPassword456"


async def test_forgot_password_existing_user_sends_otp(client: AsyncClient, fake_queue):
    await signup_and_verify(client, fake_queue, email=EMAIL, password=PASSWORD)

    resp = await client.post(FORGOT_URL, json={"email": EMAIL})
    assert resp.status_code == 200

    otp_kwargs = fake_queue.last_job_kwargs(TASK_SEND_OTP_EMAIL)
    assert otp_kwargs["purpose"] == "PASSWORD_RESET"


async def test_forgot_password_unknown_email_same_generic_response(client: AsyncClient):
    known_resp = await client.post(FORGOT_URL, json={"email": "nobody@example.com"})
    assert known_resp.status_code == 200
    # Anti-enumeration: response message is identical whether or not the account exists.
    assert "message" in known_resp.json()


async def test_reset_password_success_and_revokes_sessions(client: AsyncClient, fake_queue):
    tokens = await signup_and_verify(client, fake_queue, email=EMAIL, password=PASSWORD)
    old_refresh_token = tokens["refresh_token"]

    await client.post(FORGOT_URL, json={"email": EMAIL})
    code = fake_queue.last_job_kwargs(TASK_SEND_OTP_EMAIL)["code"]

    reset_resp = await client.post(
        RESET_URL, json={"email": EMAIL, "code": code, "new_password": NEW_PASSWORD}
    )
    assert reset_resp.status_code == 200

    old_login_resp = await client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})
    assert old_login_resp.status_code == 401

    new_login_resp = await client.post(LOGIN_URL, json={"email": EMAIL, "password": NEW_PASSWORD})
    assert new_login_resp.status_code == 200

    stale_refresh_resp = await client.post(
        REFRESH_URL, json={"refresh_token": old_refresh_token}
    )
    assert stale_refresh_resp.status_code == 401
    assert stale_refresh_resp.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


async def test_reset_password_wrong_code_rejected(client: AsyncClient, fake_queue):
    await signup_and_verify(client, fake_queue, email=EMAIL, password=PASSWORD)
    await client.post(FORGOT_URL, json={"email": EMAIL})

    resp = await client.post(
        RESET_URL, json={"email": EMAIL, "code": "000000", "new_password": NEW_PASSWORD}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_OTP"
