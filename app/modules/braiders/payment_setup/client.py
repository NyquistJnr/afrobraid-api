import asyncio
from typing import Any

import stripe

from app.core.config import get_settings

settings = get_settings()
stripe.api_key = settings.stripe_secret_key


class StripeApiError(Exception):
    pass


class StripeWebhookSignatureError(Exception):
    pass


def _create_connect_account_sync(email: str) -> str:
    account = stripe.Account.create(
        type="express",
        email=email,
        capabilities={
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
    )
    return account.id


def _create_account_link_sync(account_id: str, *, refresh_url: str, return_url: str) -> str:
    link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    return link.url


def _retrieve_account_sync(account_id: str) -> stripe.Account:
    return stripe.Account.retrieve(account_id)


async def create_connect_account(email: str) -> str:
    try:
        return await asyncio.to_thread(_create_connect_account_sync, email)
    except stripe.error.StripeError as exc:
        raise StripeApiError(f"Stripe account creation failed: {exc}") from exc


async def create_account_link(account_id: str, *, refresh_url: str, return_url: str) -> str:
    try:
        return await asyncio.to_thread(
            _create_account_link_sync, account_id, refresh_url=refresh_url, return_url=return_url
        )
    except stripe.error.StripeError as exc:
        raise StripeApiError(f"Stripe account link creation failed: {exc}") from exc


async def retrieve_account(account_id: str) -> stripe.Account:
    try:
        return await asyncio.to_thread(_retrieve_account_sync, account_id)
    except stripe.error.StripeError as exc:
        raise StripeApiError(f"Stripe account retrieval failed: {exc}") from exc


def construct_webhook_event(payload: bytes, sig_header: str | None) -> dict[str, Any]:
    if not sig_header:
        raise StripeWebhookSignatureError("Missing Stripe-Signature header")
    try:
        return stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise StripeWebhookSignatureError(str(exc)) from exc
