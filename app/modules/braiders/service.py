import uuid

from arq import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import get_settings
from app.core.exceptions import InvalidLogoUploadError, LogoNotFoundError
from app.modules.braiders import repository as braiders_repo
from app.modules.braiders.completion import (
    is_business_info_complete,
    recompute_business_info_completion,
)
from app.modules.braiders.models import (
    BioSource,
    BraiderOnboardingStatus,
    BraiderProfile,
    Gender,
)
from app.modules.braiders.schemas import (
    BusinessInfoResponse,
    BusinessInfoUpdateRequest,
    LogoConfirmRequest,
    LogoUploadUrlRequest,
    LogoUploadUrlResponse,
    OnboardingStatusResponse,
)
from app.modules.braiders.tasks import TASK_TRANSLATE_BIO

settings = get_settings()

_MAX_LOGO_SIZE_BYTES = 5 * 1024 * 1024
_ALLOWED_LOGO_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_EXTENSION_BY_CONTENT_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
_UPLOAD_URL_EXPIRES_IN_SECONDS = 300


async def _get_or_create_profile(db: AsyncSession, user_id: uuid.UUID) -> BraiderProfile:
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    if profile is None:
        profile = await braiders_repo.create_profile_for_user(db, user_id)
    return profile


async def _get_or_create_status(db: AsyncSession, user_id: uuid.UUID) -> BraiderOnboardingStatus:
    status = await braiders_repo.get_onboarding_status_by_user_id(db, user_id)
    if status is None:
        status = await braiders_repo.create_onboarding_status_for_user(db, user_id)
    return status


def _to_business_info_response(profile: BraiderProfile) -> BusinessInfoResponse:
    return BusinessInfoResponse(
        business_name=profile.business_name,
        logo_url=storage.build_public_url(profile.logo_object_key)
        if profile.logo_object_key
        else None,
        bio_en=profile.bio_en,
        bio_de=profile.bio_de,
        bio_fr=profile.bio_fr,
        bio_en_source=profile.bio_en_source,
        bio_de_source=profile.bio_de_source,
        bio_fr_source=profile.bio_fr_source,
        gender=profile.gender,
        is_complete=is_business_info_complete(profile),
    )


def _to_onboarding_status_response(status: BraiderOnboardingStatus) -> OnboardingStatusResponse:
    return OnboardingStatusResponse(
        current_step=status.current_step,
        business_info_completed_at=status.business_info_completed_at,
        veriff_completed_at=status.veriff_completed_at,
        service_type_completed_at=status.service_type_completed_at,
        portfolio_completed_at=status.portfolio_completed_at,
        service_location_completed_at=status.service_location_completed_at,
        availability_completed_at=status.availability_completed_at,
        payment_setup_completed_at=status.payment_setup_completed_at,
        completed_at=status.completed_at,
    )


async def get_business_info(db: AsyncSession, user_id: uuid.UUID) -> BusinessInfoResponse:
    profile = await _get_or_create_profile(db, user_id)
    await db.commit()
    return _to_business_info_response(profile)


async def update_business_info(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    data: BusinessInfoUpdateRequest,
    locale: str,
    queue: ArqRedis,
) -> BusinessInfoResponse:
    profile = await _get_or_create_profile(db, user_id)

    updates = data.model_dump(exclude_unset=True)
    bio_text = updates.pop("bio", None)

    if "business_name" in updates:
        profile.business_name = updates["business_name"]
    if "gender" in updates:
        gender_value = updates["gender"]
        profile.gender = Gender(gender_value) if gender_value is not None else None

    target_locales: list[str] = []
    if bio_text and bio_text != getattr(profile, f"bio_{locale}"):
        setattr(profile, f"bio_{locale}", bio_text)
        setattr(profile, f"bio_{locale}_source", BioSource.HUMAN)

        target_locales = [
            loc
            for loc in settings.supported_locales_list
            if loc != locale and getattr(profile, f"bio_{loc}_source", None) != BioSource.HUMAN
        ]
        for loc in target_locales:
            setattr(profile, f"bio_{loc}_source", BioSource.PENDING)

    await db.flush()

    status = await _get_or_create_status(db, user_id)
    recompute_business_info_completion(profile, status)
    await db.commit()

    if target_locales:
        await queue.enqueue_job(
            TASK_TRANSLATE_BIO,
            user_id=str(user_id),
            source_locale=locale,
            source_text=bio_text,
            target_locales=target_locales,
        )

    return _to_business_info_response(profile)


async def request_logo_upload_url(
    db: AsyncSession, user_id: uuid.UUID, *, data: LogoUploadUrlRequest
) -> LogoUploadUrlResponse:
    extension = _EXTENSION_BY_CONTENT_TYPE[data.content_type]
    object_key = f"braiders/{user_id}/logo/{uuid.uuid4()}.{extension}"
    upload_url = storage.generate_presigned_upload_url(
        object_key, content_type=data.content_type, expires_in=_UPLOAD_URL_EXPIRES_IN_SECONDS
    )
    return LogoUploadUrlResponse(
        upload_url=upload_url, object_key=object_key, expires_in=_UPLOAD_URL_EXPIRES_IN_SECONDS
    )


async def confirm_logo_upload(
    db: AsyncSession, user_id: uuid.UUID, *, data: LogoConfirmRequest
) -> BusinessInfoResponse:
    expected_prefix = f"braiders/{user_id}/logo/"
    if not data.object_key.startswith(expected_prefix):
        raise InvalidLogoUploadError()

    metadata = storage.head_object(data.object_key)
    if metadata is None:
        raise LogoNotFoundError()
    if (
        metadata.content_type not in _ALLOWED_LOGO_CONTENT_TYPES
        or metadata.content_length > _MAX_LOGO_SIZE_BYTES
    ):
        storage.delete_object(data.object_key)
        raise InvalidLogoUploadError()

    profile = await _get_or_create_profile(db, user_id)
    previous_object_key = profile.logo_object_key
    profile.logo_object_key = data.object_key
    await db.flush()

    status = await _get_or_create_status(db, user_id)
    recompute_business_info_completion(profile, status)
    await db.commit()

    if previous_object_key and previous_object_key != data.object_key:
        storage.delete_object(previous_object_key)

    return _to_business_info_response(profile)


async def get_onboarding_status(db: AsyncSession, user_id: uuid.UUID) -> OnboardingStatusResponse:
    status = await _get_or_create_status(db, user_id)
    await db.commit()
    return _to_onboarding_status_response(status)
