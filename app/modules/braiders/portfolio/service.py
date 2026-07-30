import uuid

from arq import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import get_settings
from app.core.exceptions import (
    InvalidPortfolioImageUploadError,
    MaxPortfolioImagesReachedError,
    PortfolioImageNotFoundError,
)
from app.modules.braiders import repository as braiders_repo
from app.modules.braiders.completion import mark_step_complete
from app.modules.braiders.models import (
    BioSource,
    BraiderOnboardingStatus,
    BraiderProfile,
    OnboardingStep,
)
from app.modules.braiders.portfolio import repository as portfolio_repo
from app.modules.braiders.portfolio.models import PortfolioImage
from app.modules.braiders.portfolio.schemas import (
    PortfolioImageConfirmRequest,
    PortfolioImageResponse,
    PortfolioImageUpdateRequest,
    PortfolioImageUploadUrlRequest,
    PortfolioImageUploadUrlResponse,
    PortfolioResponse,
)
from app.modules.braiders.portfolio.tasks import TASK_TRANSLATE_PORTFOLIO_CAPTION

settings = get_settings()

MIN_PORTFOLIO_IMAGES = 3
_MAX_PORTFOLIO_IMAGES = 20
_MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
_ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
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


def _start_caption_translation(image: PortfolioImage, locale: str, text: str) -> list[str]:
    """Same locale-fan-out as `braiders.service.update_business_info`'s bio
    handling: the locale the braider is currently using becomes the HUMAN
    source, the other supported locales are queued for translation."""
    setattr(image, f"caption_{locale}", text)
    setattr(image, f"caption_{locale}_source", BioSource.HUMAN)
    target_locales = [
        loc
        for loc in settings.supported_locales_list
        if loc != locale and getattr(image, f"caption_{loc}_source", None) != BioSource.HUMAN
    ]
    for loc in target_locales:
        setattr(image, f"caption_{loc}_source", BioSource.PENDING)
    return target_locales


def _clear_caption(image: PortfolioImage) -> None:
    for loc in settings.supported_locales_list:
        setattr(image, f"caption_{loc}", None)
        setattr(image, f"caption_{loc}_source", None)


async def _enqueue_caption_translation(
    queue: ArqRedis,
    *,
    image_id: uuid.UUID,
    source_locale: str,
    source_text: str,
    target_locales: list[str],
) -> None:
    if not target_locales:
        return
    await queue.enqueue_job(
        TASK_TRANSLATE_PORTFOLIO_CAPTION,
        image_id=str(image_id),
        source_locale=source_locale,
        source_text=source_text,
        target_locales=target_locales,
    )


def _to_image_response(image: PortfolioImage) -> PortfolioImageResponse:
    return PortfolioImageResponse(
        id=image.id,
        url=storage.build_public_url(image.object_key),
        caption_en=image.caption_en,
        caption_de=image.caption_de,
        caption_fr=image.caption_fr,
        caption_en_source=image.caption_en_source,
        caption_de_source=image.caption_de_source,
        caption_fr_source=image.caption_fr_source,
        position=image.position,
    )


async def get_portfolio(db: AsyncSession, user_id: uuid.UUID) -> PortfolioResponse:
    profile = await _get_or_create_profile(db, user_id)
    await db.commit()
    images = await portfolio_repo.list_images(db, profile.id)
    return PortfolioResponse(
        images=[_to_image_response(i) for i in images],
        min_required=MIN_PORTFOLIO_IMAGES,
        is_complete=len(images) >= MIN_PORTFOLIO_IMAGES,
    )


async def request_upload_url(
    db: AsyncSession, user_id: uuid.UUID, *, data: PortfolioImageUploadUrlRequest
) -> PortfolioImageUploadUrlResponse:
    profile = await _get_or_create_profile(db, user_id)
    await db.commit()

    existing_count = len(await portfolio_repo.list_images(db, profile.id))
    if existing_count >= _MAX_PORTFOLIO_IMAGES:
        raise MaxPortfolioImagesReachedError()

    extension = _EXTENSION_BY_CONTENT_TYPE[data.content_type]
    object_key = f"braiders/{user_id}/portfolio/{uuid.uuid4()}.{extension}"
    upload_url = storage.generate_presigned_upload_url(
        object_key, content_type=data.content_type, expires_in=_UPLOAD_URL_EXPIRES_IN_SECONDS
    )
    return PortfolioImageUploadUrlResponse(
        upload_url=upload_url, object_key=object_key, expires_in=_UPLOAD_URL_EXPIRES_IN_SECONDS
    )


async def confirm_upload(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    data: PortfolioImageConfirmRequest,
    locale: str,
    queue: ArqRedis,
) -> PortfolioImageResponse:
    expected_prefix = f"braiders/{user_id}/portfolio/"
    if not data.object_key.startswith(expected_prefix):
        raise InvalidPortfolioImageUploadError()

    metadata = storage.head_object(data.object_key)
    if metadata is None:
        raise PortfolioImageNotFoundError()
    if (
        metadata.content_type not in _ALLOWED_IMAGE_CONTENT_TYPES
        or metadata.content_length > _MAX_IMAGE_SIZE_BYTES
    ):
        storage.delete_object(data.object_key)
        raise InvalidPortfolioImageUploadError()

    profile = await _get_or_create_profile(db, user_id)
    existing_images = await portfolio_repo.list_images(db, profile.id)
    if len(existing_images) >= _MAX_PORTFOLIO_IMAGES:
        storage.delete_object(data.object_key)
        raise MaxPortfolioImagesReachedError()

    next_position = max((img.position for img in existing_images), default=-1) + 1
    image = await portfolio_repo.create_image(
        db, braider_id=profile.id, object_key=data.object_key, position=next_position
    )

    target_locales: list[str] = []
    if data.caption:
        target_locales = _start_caption_translation(image, locale, data.caption)

    if len(existing_images) + 1 >= MIN_PORTFOLIO_IMAGES:
        status = await _get_or_create_status(db, user_id)
        mark_step_complete(status, OnboardingStep.PORTFOLIO, OnboardingStep.SERVICE_LOCATION)

    await db.commit()

    if data.caption:
        await _enqueue_caption_translation(
            queue,
            image_id=image.id,
            source_locale=locale,
            source_text=data.caption,
            target_locales=target_locales,
        )

    return _to_image_response(image)


async def update_image(
    db: AsyncSession,
    user_id: uuid.UUID,
    image_id: uuid.UUID,
    *,
    data: PortfolioImageUpdateRequest,
    locale: str,
    queue: ArqRedis,
) -> PortfolioImageResponse:
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    image = await portfolio_repo.get_image_by_id(db, image_id) if profile else None
    if profile is None or image is None or image.braider_id != profile.id:
        raise PortfolioImageNotFoundError()

    target_locales: list[str] = []
    if "caption" in data.model_fields_set:
        if data.caption is None:
            _clear_caption(image)
        elif data.caption != getattr(image, f"caption_{locale}"):
            target_locales = _start_caption_translation(image, locale, data.caption)

    await db.commit()

    if target_locales:
        await _enqueue_caption_translation(
            queue,
            image_id=image.id,
            source_locale=locale,
            source_text=data.caption or "",
            target_locales=target_locales,
        )

    return _to_image_response(image)


async def delete_image(db: AsyncSession, user_id: uuid.UUID, image_id: uuid.UUID) -> None:
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    image = await portfolio_repo.get_image_by_id(db, image_id) if profile else None
    if profile is None or image is None or image.braider_id != profile.id:
        raise PortfolioImageNotFoundError()

    object_key = image.object_key
    await portfolio_repo.delete_image(db, image)
    await db.commit()
    storage.delete_object(object_key)
