from httpx import AsyncClient

from app.modules.auth.tasks import TASK_SEND_OTP_EMAIL

SIGNUP_URL = "/api/v1/auth/signup/email"
VERIFY_URL = "/api/v1/auth/verify-email"


async def signup_and_verify(
    client: AsyncClient,
    fake_queue,
    *,
    email: str,
    password: str = "Password123",
    **overrides,
) -> dict:
    payload = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": email,
        "password": password,
        "user_type": "CUSTOMER",
        **overrides,
    }
    signup_resp = await client.post(SIGNUP_URL, json=payload)
    assert signup_resp.status_code == 201, signup_resp.text

    code = fake_queue.last_job_kwargs(TASK_SEND_OTP_EMAIL)["code"]
    verify_resp = await client.post(VERIFY_URL, json={"email": email, "code": code})
    assert verify_resp.status_code == 200, verify_resp.text
    return verify_resp.json()
