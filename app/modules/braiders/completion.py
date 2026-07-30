from datetime import UTC, datetime

from app.modules.braiders.models import BraiderOnboardingStatus, BraiderProfile, OnboardingStep


def is_business_info_complete(profile: BraiderProfile) -> bool:
    return bool(
        profile.business_name
        and profile.gender
        and profile.logo_object_key
        and profile.bio_en
        and profile.bio_de
        and profile.bio_fr
    )


def recompute_business_info_completion(
    profile: BraiderProfile, status: BraiderOnboardingStatus
) -> None:
    is_complete = is_business_info_complete(profile)
    was_complete = status.business_info_completed_at is not None
    if is_complete and not was_complete:
        status.business_info_completed_at = datetime.now(UTC)
        if status.current_step == OnboardingStep.BUSINESS_INFO:
            status.current_step = OnboardingStep.VERIFF
    elif not is_complete and was_complete:
        status.business_info_completed_at = None
