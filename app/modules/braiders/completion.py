from datetime import UTC, datetime

from app.modules.braiders.models import BraiderOnboardingStatus, BraiderProfile, OnboardingStep
from app.modules.braiders.service_location.models import BraiderServiceLocation, LocationType

_STEP_ORDER = [
    OnboardingStep.BUSINESS_INFO,
    OnboardingStep.PHONE_VERIFICATION,
    OnboardingStep.VERIFF,
    OnboardingStep.SERVICE_TYPE,
    OnboardingStep.PORTFOLIO,
    OnboardingStep.SERVICE_LOCATION,
    OnboardingStep.AVAILABILITY,
    OnboardingStep.PAYMENT_SETUP,
]


def compute_current_step(status: BraiderOnboardingStatus) -> OnboardingStep:
    """The first step (in canonical order) that isn't complete yet.

    Braiders can complete steps in any order, so current_step can't just be
    advanced procedurally when a step finishes — it has to be re-derived from
    the *_completed_at fields every time, otherwise it goes stale as soon as
    someone completes a step out of sequence.
    """
    for step in _STEP_ORDER:
        field = f"{step.value.lower()}_completed_at"
        if getattr(status, field) is None:
            return step
    return OnboardingStep.COMPLETED


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
    elif not is_complete and was_complete:
        status.business_info_completed_at = None
    status.current_step = compute_current_step(status)


def is_service_location_complete(location: BraiderServiceLocation | None) -> bool:
    if location is None:
        return False
    if location.location_type is None and not location.offers_mobile:
        return False  # must offer at least one way to be reached
    if not (location.city and location.country and location.latitude and location.longitude):
        return False
    if location.location_type in (LocationType.HOME_STUDIO, LocationType.SALON) and not (
        location.address_line1 and location.postal_code
    ):
        return False
    if location.location_type == LocationType.SALON and not location.salon_name:
        return False
    return not (location.offers_mobile and not location.travel_radius_km)


def recompute_service_location_completion(
    location: BraiderServiceLocation, status: BraiderOnboardingStatus
) -> None:
    is_complete = is_service_location_complete(location)
    was_complete = status.service_location_completed_at is not None
    if is_complete and not was_complete:
        status.service_location_completed_at = datetime.now(UTC)
    elif not is_complete and was_complete:
        status.service_location_completed_at = None
    status.current_step = compute_current_step(status)


def mark_step_complete(status: BraiderOnboardingStatus, step: OnboardingStep) -> None:
    """Generic one-way step completion, for steps that don't need business-info's
    recompute-both-ways behavior (once verified/approved/etc., it stays that way)."""
    field = f"{step.value.lower()}_completed_at"
    if getattr(status, field) is None:
        setattr(status, field, datetime.now(UTC))
    status.current_step = compute_current_step(status)
