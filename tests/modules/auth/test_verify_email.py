import pytest
from httpx import AsyncClient

from tests.modules.auth.helpers import SIGNUP_URL, VERIFY_URL, signup_and_verify

pytestmark = pytest.mark.asyncio

EMAIL = "ada@example.com"


async def test_verify_email_success(client: AsyncClient, fake_queue):
    body = await signup_and_verify(client, fake_queue, email=EMAIL)

    assert body["email"] == EMAIL
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


async def test_verify_email_wrong_code(client: AsyncClient, fake_queue):
    await client.post(
        SIGNUP_URL,
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": EMAIL,
            "password": "Password123",
            "user_type": "CUSTOMER",
        },
    )

    resp = await client.post(VERIFY_URL, json={"email": EMAIL, "code": "000000"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_OTP"


async def test_verify_email_unknown_email(client: AsyncClient):
    resp = await client.post(VERIFY_URL, json={"email": "nobody@example.com", "code": "123456"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_OTP"


async def test_verify_email_too_many_attempts_locks_code(client: AsyncClient, fake_queue):
    await client.post(
        SIGNUP_URL,
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": EMAIL,
            "password": "Password123",
            "user_type": "CUSTOMER",
        },
    )

    for _ in range(5):
        resp = await client.post(VERIFY_URL, json={"email": EMAIL, "code": "000000"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_OTP"

    correct_code = fake_queue.last_job_kwargs("send_otp_email_task")["code"]
    locked_resp = await client.post(VERIFY_URL, json={"email": EMAIL, "code": correct_code})
    assert locked_resp.status_code == 400
    assert locked_resp.json()["error"]["code"] == "TOO_MANY_OTP_ATTEMPTS"
