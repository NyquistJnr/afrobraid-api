import stripe
from app.core.config import get_settings

def _get_api_key() -> str:
    return get_settings().stripe_secret_key

def _get_api_version() -> str:
    return get_settings().stripe_api_version

def create_customer(email: str, name: str) -> str:
    if get_settings().environment == "test":
        return f"cus_test_{email.split('@')[0]}"
        
    customer = stripe.Customer.create(
        email=email,
        name=name,
        api_key=_get_api_key(),
        stripe_version=_get_api_version(),
    )
    return customer.id

def create_payment_intent(
    customer_id: str,
    amount_minor: int,
    currency: str,
    metadata: dict[str, str],
    transfer_group: str,
    setup_future_usage: str | None = None,
) -> tuple[str, str]:
    """Returns (payment_intent_id, client_secret)"""
    if get_settings().environment == "test":
        return f"pi_test_{amount_minor}", "pi_test_secret"

    kwargs = {
        "customer": customer_id,
        "amount": amount_minor,
        "currency": currency.lower(),
        "payment_method_types": ["card"],
        "metadata": metadata,
        "transfer_group": transfer_group,
        "api_key": _get_api_key(),
        "stripe_version": _get_api_version(),
    }
    if setup_future_usage:
        kwargs["setup_future_usage"] = setup_future_usage

    intent = stripe.PaymentIntent.create(**kwargs)
    return intent.id, intent.client_secret
