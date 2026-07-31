from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.braiders.payment_setup import service
from app.modules.braiders.payment_setup.schemas import (
    AccountLinkResponse,
    PaymentSetupStatusResponse,
)
from app.modules.users.models import User, UserType

router = APIRouter(
    prefix="/api/v1/braiders/onboarding/payment-setup",
    tags=["Braider Onboarding - Payment Setup"],
)

_require_braider = require_roles(UserType.BRAIDER)


@router.post(
    "/account-link",
    response_model=APIResponse[AccountLinkResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Start (or resume) Stripe Connect onboarding",
    description=(
        "Creates your Stripe Express account the first time you call this, then "
        "always returns a fresh hosted onboarding link - redirect the browser "
        "there. Safe to call again if a previous link expired or you left "
        "before finishing."
    ),
)
async def create_account_link(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AccountLinkResponse]:
    result = await service.start_onboarding(db, user)
    return APIResponse(data=result)


@router.get(
    "/status",
    response_model=APIResponse[PaymentSetupStatusResponse],
    summary="Get your payment setup status",
)
async def get_status(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaymentSetupStatusResponse]:
    result = await service.get_status(db, user.id)
    return APIResponse(data=result)


@router.post(
    "/refresh",
    response_model=APIResponse[PaymentSetupStatusResponse],
    summary="Re-check your Stripe account status",
    description=(
        "Call this after returning from the Stripe onboarding flow - landing "
        "on the return URL doesn't itself mean onboarding finished, so poll "
        "here (or wait for the webhook) to get the up-to-date status."
    ),
)
async def refresh_status(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaymentSetupStatusResponse]:
    result = await service.refresh_status(db, user.id)
    return APIResponse(data=result)
