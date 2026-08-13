"""Raw PayPal REST API wrapper (Orders v2) for the platform account's
checkout flow - the PayPal counterpart to client.py's Stripe PaymentIntent
wrapper.

Short-circuits entirely in the test environment and returns deterministic
fakes, exactly as client.py does, so booking tests don't need to mock
PayPal either.
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.money import from_minor_units

settings = get_settings()

_IS_TEST_ENV = settings.environment == "test"

_TIMEOUT = 10.0


class PaypalApiError(Exception):
    pass


class PaypalWebhookSignatureError(Exception):
    pass


@dataclass(frozen=True)
class PaypalOrderResult:
    id: str


@dataclass(frozen=True)
class PaypalCaptureResult:
    capture_id: str
    status: str


# Module-level OAuth2 token cache - client-credentials tokens are valid for
# hours, and creating a booking is a hot path, so it's worth avoiding a
# token fetch on every order/capture call. Safe under asyncio's single
# event loop; the lock only prevents a thundering herd of concurrent
# refreshes.
_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}
_token_lock = asyncio.Lock()


async def _get_access_token() -> str:
    if _token_cache["access_token"] and time.monotonic() < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    async with _token_lock:
        if _token_cache["access_token"] and time.monotonic() < _token_cache["expires_at"]:
            return _token_cache["access_token"]
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    f"{settings.paypal_api_base_url}/v1/oauth2/token",
                    auth=(settings.paypal_client_id, settings.paypal_client_secret),
                    data={"grant_type": "client_credentials"},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise PaypalApiError(f"PayPal OAuth token request failed: {exc}") from exc

        # Refresh a minute early so a call started just before expiry doesn't race it.
        _token_cache["access_token"] = data["access_token"]
        _token_cache["expires_at"] = time.monotonic() + max(int(data["expires_in"]) - 60, 0)
        return _token_cache["access_token"]


async def create_order(
    *,
    amount_minor: int,
    currency: str,
    booking_id: str,
    purpose: str,
    idempotency_key: str,
) -> PaypalOrderResult:
    if _IS_TEST_ENV:
        return PaypalOrderResult(id=f"paypal_order_test_{uuid.uuid4().hex[:24]}")

    token = await _get_access_token()
    amount_value = str(from_minor_units(amount_minor))
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{settings.paypal_api_base_url}/v2/checkout/orders",
                headers={"Authorization": f"Bearer {token}", "PayPal-Request-Id": idempotency_key},
                json={
                    "intent": "CAPTURE",
                    "purchase_units": [
                        {
                            "custom_id": f"{booking_id}:{purpose}",
                            "amount": {"currency_code": currency.upper(), "value": amount_value},
                        }
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
        return PaypalOrderResult(id=data["id"])
    except (httpx.HTTPError, KeyError) as exc:
        raise PaypalApiError(f"PayPal order creation failed: {exc}") from exc


async def capture_order(order_id: str) -> PaypalCaptureResult:
    if _IS_TEST_ENV:
        return PaypalCaptureResult(capture_id=f"paypal_capture_test_{uuid.uuid4().hex[:24]}", status="COMPLETED")

    token = await _get_access_token()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{settings.paypal_api_base_url}/v2/checkout/orders/{order_id}/capture",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()
        capture = data["purchase_units"][0]["payments"]["captures"][0]
        return PaypalCaptureResult(capture_id=capture["id"], status=capture["status"])
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        raise PaypalApiError(f"PayPal order capture failed: {exc}") from exc


async def construct_webhook_event(headers: dict[str, str], raw_body: bytes) -> dict[str, Any]:
    """PayPal has no local HMAC verification like Stripe - signature
    verification is itself an API call against the transmission headers."""
    transmission_id = headers.get("paypal-transmission-id")
    transmission_time = headers.get("paypal-transmission-time")
    cert_url = headers.get("paypal-cert-url")
    auth_algo = headers.get("paypal-auth-algo")
    transmission_sig = headers.get("paypal-transmission-sig")
    if not all([transmission_id, transmission_time, cert_url, auth_algo, transmission_sig]):
        raise PaypalWebhookSignatureError("Missing PayPal webhook transmission headers")

    try:
        event = json.loads(raw_body)
    except ValueError as exc:
        raise PaypalWebhookSignatureError(f"Invalid PayPal webhook payload: {exc}") from exc

    if _IS_TEST_ENV:
        return event

    token = await _get_access_token()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{settings.paypal_api_base_url}/v1/notifications/verify-webhook-signature",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "transmission_id": transmission_id,
                    "transmission_time": transmission_time,
                    "cert_url": cert_url,
                    "auth_algo": auth_algo,
                    "transmission_sig": transmission_sig,
                    "webhook_id": settings.paypal_webhook_id,
                    "webhook_event": event,
                },
            )
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPError as exc:
        raise PaypalWebhookSignatureError(str(exc)) from exc

    if result.get("verification_status") != "SUCCESS":
        raise PaypalWebhookSignatureError("PayPal webhook signature verification failed")

    return event
