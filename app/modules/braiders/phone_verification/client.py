import asyncio
from functools import lru_cache

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from app.core.config import get_settings

settings = get_settings()


class TwilioVerificationError(Exception):
    pass


@lru_cache
def _get_client() -> Client:
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def _send_verification_code_sync(phone_number: str) -> str:
    verification = (
        _get_client()
        .verify.v2.services(settings.twilio_verify_service_sid)
        .verifications.create(to=phone_number, channel="sms")
    )
    return verification.status


def _check_verification_code_sync(phone_number: str, code: str) -> str:
    check = (
        _get_client()
        .verify.v2.services(settings.twilio_verify_service_sid)
        .verification_checks.create(to=phone_number, code=code)
    )
    return check.status


async def send_verification_code(phone_number: str) -> str:
    if settings.phone_verification_bypass_enabled:
        return "pending"

    try:
        return await asyncio.to_thread(_send_verification_code_sync, phone_number)
    except TwilioRestException as exc:
        raise TwilioVerificationError(f"Twilio send-code failed: {exc}") from exc


async def check_verification_code(phone_number: str, code: str) -> str:
    if settings.phone_verification_bypass_enabled:
        return "approved" if code == settings.phone_verification_bypass_code else "denied"

    try:
        return await asyncio.to_thread(_check_verification_code_sync, phone_number, code)
    except TwilioRestException as exc:
        raise TwilioVerificationError(f"Twilio verify-code failed: {exc}") from exc
