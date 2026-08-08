import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.tasks import TASK_SEND_OTP_EMAIL
from app.modules.users.models import User

pytestmark = pytest.mark.asyncio

SIGNUP_URL = "/api/v1/auth/signup/email"


def _valid_payload(**overrides) -> dict:
    payload = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "password": "Password123",
        "user_type": "CUSTOMER",
    }
    payload.update(overrides)
    return payload


async def test_signup_email_success(client: AsyncClient, db_session: AsyncSession, fake_queue):
    resp = await client.post(SIGNUP_URL, json=_valid_payload())

    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["email"] == "ada@example.com"

    result = await db_session.execute(select(User).where(User.email == "ada@example.com"))
    user = result.scalar_one()
    assert user.is_email_verified is False
    assert user.user_type.value == "CUSTOMER"
    assert user.password_hash is not None

    otp_kwargs = fake_queue.last_job_kwargs(TASK_SEND_OTP_EMAIL)
    assert otp_kwargs["to"] == "ada@example.com"
    assert otp_kwargs["purpose"] == "EMAIL_VERIFICATION"
    assert len(otp_kwargs["code"]) == 6


async def test_signup_email_duplicate_rejected(client: AsyncClient):
    first = await client.post(SIGNUP_URL, json=_valid_payload())
    assert first.status_code == 201

    second = await client.post(SIGNUP_URL, json=_valid_payload(first_name="Grace"))
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


async def test_signup_admin_user_type_rejected(client: AsyncClient):
    resp = await client.post(SIGNUP_URL, json=_valid_payload(user_type="ADMIN"))
    assert resp.status_code == 422


async def test_signup_weak_password_rejected(client: AsyncClient):
    resp = await client.post(SIGNUP_URL, json=_valid_payload(password="short"))
    assert resp.status_code == 422


async def test_signup_duplicate_phone_rejected(client: AsyncClient):
    first = await client.post(SIGNUP_URL, json=_valid_payload(phone_number="+491234567890"))
    assert first.status_code == 201

    second = await client.post(
        SIGNUP_URL,
        json=_valid_payload(email="grace@example.com", phone_number="+491234567890"),
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "PHONE_ALREADY_EXISTS"
