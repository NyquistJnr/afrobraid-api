import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.exceptions import (
    BraiderStyleAddonInvalidError,
    BraiderStyleAlreadyExistsError,
    BraiderStyleNotFoundError,
    BraiderStyleVariationInvalidError,
    EntityInUseError,
    StyleNotActiveError,
    StyleNotFoundError,
)
from app.core.pagination import PaginatedData, PaginationMeta, PaginationParams, paginate
from app.modules.braiders import repository as braiders_repo
from app.modules.braiders.completion import mark_step_complete
from app.modules.braiders.models import OnboardingStep
from app.modules.braiders.offerings import repository as offerings_repo
from app.modules.braiders.offerings.models import BraiderStyle
from app.modules.braiders.offerings.schemas import (
    BraiderStyleAddonResponse,
    BraiderStyleCreateRequest,
    BraiderStyleResponse,
    BraiderStyleUpdateRequest,
    BraiderStyleVariationResponse,
)
from app.modules.styles import repository as styles_repo


async def _to_response(db: AsyncSession, braider_style: BraiderStyle) -> BraiderStyleResponse:
    style = await styles_repo.get_style_by_id(db, braider_style.style_id)
    # styles.id has no ON DELETE from braider_styles, so a referenced style
    # can't have been removed out from under this row.
    assert style is not None
    images = await styles_repo.list_style_images(db, braider_style.style_id)
    primary_image_url = storage.build_public_url(images[0].object_key) if images else None

    variations = []
    for variation_row in await offerings_repo.list_braider_style_variations(db, braider_style.id):
        variation = await styles_repo.get_style_variation_by_id(
            db, variation_row.style_variation_id
        )
        # Same guarantee as `style` above, via the FK on style_variation_id.
        assert variation is not None
        variations.append(
            BraiderStyleVariationResponse(
                id=variation_row.id,
                style_variation_id=variation_row.style_variation_id,
                name_en=variation.name_en,
                name_de=variation.name_de,
                name_fr=variation.name_fr,
                price=variation_row.price,
            )
        )

    addons = []
    for addon_row in await offerings_repo.list_braider_style_addons(db, braider_style.id):
        addon = await styles_repo.get_addon_by_id(db, addon_row.addon_id)
        # Same guarantee as `style` above, via the FK on addon_id.
        assert addon is not None
        addons.append(
            BraiderStyleAddonResponse(
                id=addon_row.id,
                addon_id=addon_row.addon_id,
                name_en=addon.name_en,
                name_de=addon.name_de,
                name_fr=addon.name_fr,
                price=addon_row.price,
                is_required=addon_row.is_required,
            )
        )

    return BraiderStyleResponse(
        id=braider_style.id,
        style_id=braider_style.style_id,
        style_slug=style.slug,
        style_name_en=style.name_en,
        style_name_de=style.name_de,
        style_name_fr=style.name_fr,
        primary_image_url=primary_image_url,
        base_price=braider_style.base_price,
        duration_minutes=braider_style.duration_minutes,
        is_active=braider_style.is_active,
        variations=variations,
        addons=addons,
    )


async def list_braider_styles(
    db: AsyncSession, user_id: uuid.UUID, *, params: PaginationParams
) -> PaginatedData[BraiderStyleResponse]:
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    if profile is None:
        return PaginatedData(
            items=[],
            pagination=PaginationMeta(
                page=params.page,
                page_size=params.page_size,
                total_items=0,
                total_pages=0,
                has_next=False,
                has_previous=False,
            ),
        )

    stmt = offerings_repo.build_braider_styles_stmt(profile.id)
    rows, meta = await paginate(db, stmt, params)
    items = [await _to_response(db, row) for row in rows]
    return PaginatedData(items=items, pagination=meta)


async def get_braider_style(
    db: AsyncSession, user_id: uuid.UUID, braider_style_id: uuid.UUID
) -> BraiderStyleResponse:
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    braider_style = (
        await offerings_repo.get_braider_style_by_id(db, braider_style_id) if profile else None
    )
    if profile is None or braider_style is None or braider_style.braider_id != profile.id:
        raise BraiderStyleNotFoundError()
    return await _to_response(db, braider_style)


async def create_braider_style(
    db: AsyncSession, user_id: uuid.UUID, *, data: BraiderStyleCreateRequest
) -> BraiderStyleResponse:
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    if profile is None:
        profile = await braiders_repo.create_profile_for_user(db, user_id)

    style = await styles_repo.get_style_by_id(db, data.style_id)
    if style is None:
        raise StyleNotFoundError()
    if not style.is_active:
        raise StyleNotActiveError()

    existing = await offerings_repo.get_braider_style_by_style_id(db, profile.id, data.style_id)
    if existing is not None:
        raise BraiderStyleAlreadyExistsError()

    for v in data.variations:
        variation = await styles_repo.get_style_variation_by_id(db, v.style_variation_id)
        if variation is None or variation.style_id != style.id or not variation.is_active:
            raise BraiderStyleVariationInvalidError()

    for a in data.addons:
        addon = await styles_repo.get_addon_by_id(db, a.addon_id)
        if addon is None or not addon.is_active:
            raise BraiderStyleAddonInvalidError()

    braider_style = await offerings_repo.create_braider_style(
        db,
        braider_id=profile.id,
        style_id=data.style_id,
        base_price=data.base_price,
        duration_minutes=data.duration_minutes,
    )
    for v in data.variations:
        await offerings_repo.create_braider_style_variation(
            db,
            braider_style_id=braider_style.id,
            style_variation_id=v.style_variation_id,
            price=v.price,
        )
    for a in data.addons:
        await offerings_repo.create_braider_style_addon(
            db,
            braider_style_id=braider_style.id,
            addon_id=a.addon_id,
            price=a.price,
            is_required=a.is_required,
        )

    onboarding_status = await braiders_repo.get_onboarding_status_by_user_id(db, user_id)
    if onboarding_status is None:
        onboarding_status = await braiders_repo.create_onboarding_status_for_user(db, user_id)
    mark_step_complete(onboarding_status, OnboardingStep.SERVICE_TYPE)

    await db.commit()
    return await _to_response(db, braider_style)


async def update_braider_style(
    db: AsyncSession,
    user_id: uuid.UUID,
    braider_style_id: uuid.UUID,
    *,
    data: BraiderStyleUpdateRequest,
) -> BraiderStyleResponse:
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    braider_style = (
        await offerings_repo.get_braider_style_by_id(db, braider_style_id) if profile else None
    )
    if profile is None or braider_style is None or braider_style.braider_id != profile.id:
        raise BraiderStyleNotFoundError()

    if data.base_price is not None:
        braider_style.base_price = data.base_price
    if data.duration_minutes is not None:
        braider_style.duration_minutes = data.duration_minutes
    if data.is_active is not None:
        braider_style.is_active = data.is_active

    if data.variations is not None:
        for v in data.variations:
            variation = await styles_repo.get_style_variation_by_id(db, v.style_variation_id)
            if (
                variation is None
                or variation.style_id != braider_style.style_id
                or not variation.is_active
            ):
                raise BraiderStyleVariationInvalidError()
        await offerings_repo.delete_braider_style_variations(db, braider_style.id)
        for v in data.variations:
            await offerings_repo.create_braider_style_variation(
                db,
                braider_style_id=braider_style.id,
                style_variation_id=v.style_variation_id,
                price=v.price,
            )

    if data.addons is not None:
        for a in data.addons:
            addon = await styles_repo.get_addon_by_id(db, a.addon_id)
            if addon is None or not addon.is_active:
                raise BraiderStyleAddonInvalidError()
        await offerings_repo.delete_braider_style_addons(db, braider_style.id)
        for a in data.addons:
            await offerings_repo.create_braider_style_addon(
                db,
                braider_style_id=braider_style.id,
                addon_id=a.addon_id,
                price=a.price,
                is_required=a.is_required,
            )

    await db.commit()
    return await _to_response(db, braider_style)


async def delete_braider_style(
    db: AsyncSession, user_id: uuid.UUID, braider_style_id: uuid.UUID
) -> None:
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    braider_style = (
        await offerings_repo.get_braider_style_by_id(db, braider_style_id) if profile else None
    )
    if profile is None or braider_style is None or braider_style.braider_id != profile.id:
        raise BraiderStyleNotFoundError()

    try:
        await offerings_repo.delete_braider_style(db, braider_style)
        await db.commit()
    except IntegrityError:
        # bookings.braider_style_id has no ON DELETE CASCADE (see the
        # model/migration) precisely so this can't happen silently - a
        # style that's ever been booked must be deactivated, not deleted.
        await db.rollback()
        raise EntityInUseError() from None
