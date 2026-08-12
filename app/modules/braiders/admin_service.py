import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BraiderNotFoundError
from app.modules.braiders import repository as braiders_repo
from app.modules.braiders.completion import compute_current_step
from app.modules.braiders.models import OnboardingStep
from app.modules.braiders.schemas import (
    AdminBraiderOnboardingResponse,
    AdminBraiderOnboardingStepResponse,
)

_ONBOARDING_STEP_FIELDS: tuple[tuple[OnboardingStep, str], ...] = (
    (OnboardingStep.BUSINESS_INFO, "business_info_completed_at"),
    (OnboardingStep.PHONE_VERIFICATION, "phone_verification_completed_at"),
    (OnboardingStep.VERIFF, "veriff_completed_at"),
    (OnboardingStep.SERVICE_TYPE, "service_type_completed_at"),
    (OnboardingStep.PORTFOLIO, "portfolio_completed_at"),
    (OnboardingStep.SERVICE_LOCATION, "service_location_completed_at"),
    (OnboardingStep.AVAILABILITY, "availability_completed_at"),
    (OnboardingStep.PAYMENT_SETUP, "payment_setup_completed_at"),
)


async def get_braider_onboarding(
    db: AsyncSession, braider_id: uuid.UUID
) -> AdminBraiderOnboardingResponse:
    profile = await braiders_repo.get_profile_by_id(db, braider_id)
    if profile is None:
        raise BraiderNotFoundError()

    status = await braiders_repo.get_onboarding_status_by_user_id(db, profile.user_id)
    if status is None:
        return AdminBraiderOnboardingResponse(
            braider_id=profile.id,
            user_id=profile.user_id,
            current_step=OnboardingStep.BUSINESS_INFO,
            completed_at=None,
            steps=[
                AdminBraiderOnboardingStepResponse(
                    step=step, completed=False, completed_at=None
                )
                for step, _ in _ONBOARDING_STEP_FIELDS
            ],
        )

    current_step = compute_current_step(status)
    return AdminBraiderOnboardingResponse(
        braider_id=profile.id,
        user_id=profile.user_id,
        current_step=current_step,
        completed_at=status.completed_at,
        steps=[
            AdminBraiderOnboardingStepResponse(
                step=step,
                completed=getattr(status, field_name) is not None,
                completed_at=getattr(status, field_name),
            )
            for step, field_name in _ONBOARDING_STEP_FIELDS
        ],
    )
