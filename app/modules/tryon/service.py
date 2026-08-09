import uuid

from arq import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import get_settings
from app.core.exceptions import (
    InvalidTryOnImageUploadError,
    MaxPendingTryOnsReachedError,
    StyleNotActiveError,
    StyleNotFoundError,
    TryOnNotFoundError,
    TryOnStyleOrDescriptionRequiredError,
    TryOnStyleVariationInvalidError,
)
from app.core.i18n import localize_field, t
from app.modules.styles import repository as styles_repo
from app.modules.styles.models import Style, StyleVariation
from app.modules.tryon import repository as tryon_repo
from app.modules.tryon.models import HairstyleTryOn, TryOnStatus
from app.modules.tryon.schemas import (
    TryOnCreateRequest,
    TryOnResponse,
    TryOnStyleSummary,
    TryOnStyleVariationSummary,
    TryOnUploadUrlRequest,
    TryOnUploadUrlResponse,
)
from app.modules.tryon.tasks import TASK_GENERATE_HAIRSTYLE_TRYON

settings = get_settings()

_MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
_ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_EXTENSION_BY_CONTENT_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
_UPLOAD_URL_EXPIRES_IN_SECONDS = 300


async def request_upload_url(
    user_id: uuid.UUID, *, data: TryOnUploadUrlRequest
) -> TryOnUploadUrlResponse:
    extension = _EXTENSION_BY_CONTENT_TYPE[data.content_type]
    object_key = f"tryon/{user_id}/original/{uuid.uuid4()}.{extension}"
    upload_url = storage.generate_presigned_upload_url(
        object_key, content_type=data.content_type, expires_in=_UPLOAD_URL_EXPIRES_IN_SECONDS
    )
    return TryOnUploadUrlResponse(
        upload_url=upload_url, object_key=object_key, expires_in=_UPLOAD_URL_EXPIRES_IN_SECONDS
    )


async def _resolve_style(
    db: AsyncSession, style_id: uuid.UUID | None, style_variation_id: uuid.UUID | None
) -> tuple[Style | None, StyleVariation | None]:
    if style_id is None:
        if style_variation_id is not None:
            raise TryOnStyleVariationInvalidError()
        return None, None

    style = await styles_repo.get_style_by_id(db, style_id)
    if style is None:
        raise StyleNotFoundError()
    if not style.is_active:
        raise StyleNotActiveError()

    variation: StyleVariation | None = None
    if style_variation_id is not None:
        variation = await styles_repo.get_style_variation_by_id(db, style_variation_id)
        if variation is None or variation.style_id != style.id:
            raise TryOnStyleVariationInvalidError()

    return style, variation


def _build_prompt(
    *, style: Style | None, variation: StyleVariation | None, description: str | None, locale: str
) -> str:
    parts: list[str] = []
    if style is not None:
        piece = localize_field(style, "name", locale) or style.slug
        style_description = localize_field(style, "description", locale)
        if style_description:
            piece = f"{piece} ({style_description})"
        parts.append(piece)
    if variation is not None:
        variation_name = localize_field(variation, "name", locale)
        if variation_name:
            parts.append(variation_name)
    if description:
        parts.append(description)

    requested = "; ".join(parts)
    return (
        f"Change the person's hairstyle to: {requested}. Keep the same face, skin tone, "
        "expression, and background - only change the hair."
    )


async def create_tryon(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    data: TryOnCreateRequest,
    locale: str,
    queue: ArqRedis,
) -> TryOnResponse:
    if data.style_id is None and not data.description:
        raise TryOnStyleOrDescriptionRequiredError()

    expected_prefix = f"tryon/{user_id}/original/"
    if not data.object_key.startswith(expected_prefix):
        raise InvalidTryOnImageUploadError()

    metadata = storage.head_object(data.object_key)
    if metadata is None:
        raise InvalidTryOnImageUploadError()
    if (
        metadata.content_type not in _ALLOWED_IMAGE_CONTENT_TYPES
        or metadata.content_length > _MAX_IMAGE_SIZE_BYTES
    ):
        storage.delete_object(data.object_key)
        raise InvalidTryOnImageUploadError()

    style, variation = await _resolve_style(db, data.style_id, data.style_variation_id)

    pending_count = await tryon_repo.count_pending_for_user(db, user_id)
    if pending_count >= settings.tryon_max_pending_per_user:
        storage.delete_object(data.object_key)
        raise MaxPendingTryOnsReachedError(limit=settings.tryon_max_pending_per_user)

    prompt = _build_prompt(
        style=style, variation=variation, description=data.description, locale=locale
    )

    tryon = await tryon_repo.create_tryon(
        db,
        user_id=user_id,
        style_id=style.id if style else None,
        style_variation_id=variation.id if variation else None,
        description=data.description,
        prompt=prompt,
        source_object_key=data.object_key,
    )
    await db.commit()

    await queue.enqueue_job(TASK_GENERATE_HAIRSTYLE_TRYON, tryon_id=str(tryon.id))

    return await _to_response(db, tryon, locale=locale)


async def get_tryon(
    db: AsyncSession, user_id: uuid.UUID, tryon_id: uuid.UUID, *, locale: str
) -> TryOnResponse:
    tryon = await tryon_repo.get_tryon_by_id(db, tryon_id)
    if tryon is None or tryon.user_id != user_id:
        raise TryOnNotFoundError()
    return await _to_response(db, tryon, locale=locale)


async def list_tryons(db: AsyncSession, user_id: uuid.UUID, *, locale: str) -> list[TryOnResponse]:
    tryons = await tryon_repo.list_tryons_for_user(db, user_id)
    return [await _to_response(db, tryon, locale=locale) for tryon in tryons]


async def delete_tryon(db: AsyncSession, user_id: uuid.UUID, tryon_id: uuid.UUID) -> None:
    tryon = await tryon_repo.get_tryon_by_id(db, tryon_id)
    if tryon is None or tryon.user_id != user_id:
        raise TryOnNotFoundError()

    source_key, result_key = tryon.source_object_key, tryon.result_object_key
    await tryon_repo.delete_tryon(db, tryon)
    await db.commit()

    if source_key:
        storage.delete_object(source_key)
    if result_key:
        storage.delete_object(result_key)


async def _to_response(db: AsyncSession, tryon: HairstyleTryOn, *, locale: str) -> TryOnResponse:
    style_summary = None
    if tryon.style_id:
        style = await styles_repo.get_style_by_id(db, tryon.style_id)
        if style:
            style_summary = TryOnStyleSummary(
                id=style.id,
                slug=style.slug,
                name=localize_field(style, "name", locale) or style.slug,
            )

    variation_summary = None
    if tryon.style_variation_id:
        variation = await styles_repo.get_style_variation_by_id(db, tryon.style_variation_id)
        if variation:
            variation_summary = TryOnStyleVariationSummary(
                id=variation.id,
                name=localize_field(variation, "name", locale) or "",
            )

    return TryOnResponse(
        id=tryon.id,
        status=tryon.status,
        style=style_summary,
        style_variation=variation_summary,
        description=tryon.description,
        original_url=storage.build_public_url(tryon.source_object_key)
        if tryon.source_object_key
        else None,
        result_url=storage.build_public_url(tryon.result_object_key)
        if tryon.result_object_key
        else None,
        error_message=t("tryon.generation_failed", locale)
        if tryon.status == TryOnStatus.FAILED
        else None,
        created_at=tryon.created_at,
    )
