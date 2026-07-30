import hashlib
import hmac
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings

settings = get_settings()


class VeriffApiError(Exception):
    pass


@dataclass
class VeriffSessionResult:
    session_id: str
    verification_url: str
    status: str


def sign(payload: str) -> str:
    return hmac.new(
        settings.veriff_secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(raw_body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    expected = hmac.new(settings.veriff_secret_key.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def create_session(*, first_name: str, last_name: str, vendor_data: str) -> VeriffSessionResult:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.veriff_api_url}/sessions",
                headers={"X-AUTH-CLIENT": settings.veriff_api_key, "Content-Type": "application/json"},
                json={
                    "verification": {
                        "callback": settings.veriff_callback_url,
                        "vendorData": vendor_data,
                        "person": {"firstName": first_name, "lastName": last_name},
                    }
                },
            )
            response.raise_for_status()
            data = response.json()
            verification = data["verification"]
            return VeriffSessionResult(
                session_id=verification["id"],
                verification_url=verification["url"],
                status=verification["status"],
            )
    except (httpx.HTTPError, KeyError) as exc:
        raise VeriffApiError(f"Veriff session creation failed: {exc}") from exc


async def get_decision(session_id: str) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.veriff_api_url}/sessions/{session_id}/decision",
                headers={
                    "X-AUTH-CLIENT": settings.veriff_api_key,
                    "X-HMAC-SIGNATURE": sign(session_id),
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("verification")
    except httpx.HTTPError as exc:
        raise VeriffApiError(f"Veriff decision poll failed: {exc}") from exc
