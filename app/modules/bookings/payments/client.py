"""Raw Stripe SDK wrapper for the platform account's payment flow (customers
and PaymentIntents) - separate from `braiders/payment_setup/client.py`,
which talks to Connect accounts.

Short-circuits entirely in the test environment and returns deterministic
fakes, exactly as `shared/translation/client.py` does - this is what lets
every booking test run without mocking Stripe (see the plan's verification
section: "the highest-leverage test decision").
"""

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

import stripe

from app.core.config import get_settings

settings = get_settings()
stripe.api_key = settings.stripe_secret_key
# Pinned so Stripe can't reshape request/response/webhook payloads under this
# app on their own release schedule (design correction #8).
stripe.api_version = settings.stripe_api_version

_IS_TEST_ENV = settings.environment == "test"


class StripeApiError(Exception):
    pass


class StripeWebhookSignatureError(Exception):
    pass


class StripeCardError(Exception):
    """An off-session charge's CardError - raised synchronously by
    `charge_off_session` (design correction #13: off-session failure is not
    a webhook-driven state, Stripe returns/raises it inline). `code` is
    Stripe's decline/error code (e.g. `card_declined`, `expired_card`,
    `authentication_required`) and is what the balance-charge retry ladder
    branches on."""

    def __init__(self, *, code: str | None, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class PaymentIntentResult:
    id: str
    client_secret: str


def _create_customer_sync(*, email: str, name: str) -> str:
    customer = stripe.Customer.create(email=email, name=name)
    return customer.id


def _create_payment_intent_sync(
    *,
    amount_minor: int,
    currency: str,
    customer_id: str,
    metadata: dict[str, str],
    off_session_setup: bool,
) -> PaymentIntentResult:
    # Deliberately no `payment_method_types` here - omitting it turns on
    # Stripe's dynamic payment methods, which shows/ranks whichever methods
    # are enabled in the Dashboard (Settings > Payment methods) for this
    # customer's currency/location/amount, e.g. PayPal for EU-based
    # customers, with no backend changes needed to add or remove one.
    kwargs: dict[str, Any] = {
        "amount": amount_minor,
        "currency": currency.lower(),
        "customer": customer_id,
        "metadata": metadata,
    }
    if off_session_setup:
        # Persists the payment method for a later off-session charge (the
        # balance, months out) - the mandate disclosure this requires is a
        # network requirement, shown client-side before confirmation (design
        # correction #13), not something this backend call can express.
        kwargs["setup_future_usage"] = "off_session"
    intent = stripe.PaymentIntent.create(**kwargs)
    return PaymentIntentResult(id=intent.id, client_secret=intent.client_secret)


async def create_customer(*, email: str, name: str) -> str:
    if _IS_TEST_ENV:
        return f"cus_test_{uuid.uuid4().hex[:24]}"
    try:
        return await asyncio.to_thread(_create_customer_sync, email=email, name=name)
    except stripe.error.StripeError as exc:
        raise StripeApiError(f"Stripe customer creation failed: {exc}") from exc


async def create_payment_intent(
    *,
    amount_minor: int,
    currency: str,
    customer_id: str,
    metadata: dict[str, str],
    off_session_setup: bool = False,
) -> PaymentIntentResult:
    if _IS_TEST_ENV:
        pi_id = f"pi_test_{uuid.uuid4().hex[:24]}"
        return PaymentIntentResult(id=pi_id, client_secret=f"{pi_id}_secret_test")
    try:
        return await asyncio.to_thread(
            _create_payment_intent_sync,
            amount_minor=amount_minor,
            currency=currency,
            customer_id=customer_id,
            metadata=metadata,
            off_session_setup=off_session_setup,
        )
    except stripe.error.StripeError as exc:
        raise StripeApiError(f"Stripe payment intent creation failed: {exc}") from exc


def _charge_off_session_sync(
    *,
    amount_minor: int,
    currency: str,
    customer_id: str,
    payment_method_id: str,
    metadata: dict[str, str],
    idempotency_key: str,
) -> PaymentIntentResult:
    # Unlike the on-session intent above, this one explicitly pins
    # payment_method_types to ["card"] (design correction #13) - PayPal,
    # iDEAL, Bancontact etc. give no reusable off-session mandate, so
    # letting Stripe's dynamic payment methods pick one here would be wrong
    # even though it's what create_payment_intent wants for the on-session
    # deposit/full charge.
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_minor,
            currency=currency.lower(),
            customer=customer_id,
            payment_method=payment_method_id,
            payment_method_types=["card"],
            off_session=True,
            confirm=True,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
    except stripe.error.CardError as exc:
        error = getattr(exc, "error", None)
        raise StripeCardError(
            code=getattr(error, "code", None), message=exc.user_message or str(exc)
        ) from exc
    return PaymentIntentResult(id=intent.id, client_secret=intent.client_secret)


async def charge_off_session(
    *,
    amount_minor: int,
    currency: str,
    customer_id: str,
    payment_method_id: str,
    metadata: dict[str, str],
    idempotency_key: str,
) -> PaymentIntentResult:
    if _IS_TEST_ENV:
        pi_id = f"pi_test_{uuid.uuid4().hex[:24]}"
        return PaymentIntentResult(id=pi_id, client_secret=f"{pi_id}_secret_test")
    try:
        return await asyncio.to_thread(
            _charge_off_session_sync,
            amount_minor=amount_minor,
            currency=currency,
            customer_id=customer_id,
            payment_method_id=payment_method_id,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
    except StripeCardError:
        raise
    except stripe.error.StripeError as exc:
        raise StripeApiError(f"Stripe off-session charge failed: {exc}") from exc


def construct_payments_webhook_event(payload: bytes, sig_header: str | None) -> dict[str, Any]:
    if not sig_header:
        raise StripeWebhookSignatureError("Missing Stripe-Signature header")
    try:
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_payments_webhook_secret
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise StripeWebhookSignatureError(str(exc)) from exc
