from pydantic import BaseModel


class AccountLinkResponse(BaseModel):
    onboarding_url: str


class PaymentSetupStatusResponse(BaseModel):
    has_account: bool
    stripe_account_id: str | None = None
    charges_enabled: bool = False
    payouts_enabled: bool = False
    details_submitted: bool = False
    disabled_reason: str | None = None
    requirements_currently_due: list[str] = []
    is_complete: bool = False
