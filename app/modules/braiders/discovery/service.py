import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.exceptions import (
    BraiderNotFoundError,
    InvalidSearchDateRangeError,
    InvalidSearchLocationError,
    InvalidSearchPriceRangeError,
)
from app.core.i18n import localize_field
from app.core.pagination import PaginatedData, PaginationMeta, PaginationParams
from app.modules.braiders.discovery import repository as discovery_repo
from app.modules.braiders.discovery.schemas import (
    BraiderDetailResponse,
    BraiderLocationResponse,
    BraiderOfferedStyleResponse,
    BraiderSearchItemResponse,
    BraiderStyleAddonPublicResponse,
    BraiderStyleVariationPublicResponse,
    MatchedStyleResponse,
    PortfolioImagePublicResponse,
)
from app.modules.braiders.offerings import repository as offerings_repo
from app.modules.braiders.offerings.models import BraiderStyle
from app.modules.braiders.portfolio import repository as portfolio_repo
from app.modules.braiders.service_location import repository as service_location_repo
from app.modules.braiders.service_location.models import BraiderServiceLocation, LocationType
from app.modules.styles import repository as styles_repo
from app.modules.styles.models import Style

_MAX_DATE_RANGE_DAYS = 90
_MAX_SEARCH_STYLES = 5


async def _paginate_rows(db: AsyncSession, stmt, params: PaginationParams):
    """Same COUNT/LIMIT/OFFSET shape as `app.core.pagination.paginate`, but
    returns raw `Row`s instead of `.scalars()` - the search query selects
    multiple joined entities per row (profile, location, distance, ...),
    and `.scalars()` would silently keep only the first column."""
    total_items = (
        await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ) or 0

    result = await db.execute(stmt.limit(params.page_size).offset(params.offset))
    rows = result.all()

    total_pages = -(-total_items // params.page_size) if total_items else 0
    meta = PaginationMeta(
        page=params.page,
        page_size=params.page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=params.page < total_pages,
        has_previous=params.page > 1,
    )
    return rows, meta


def _to_matched_style_response(
    braider_style: BraiderStyle, style: Style, locale: str
) -> MatchedStyleResponse:
    return MatchedStyleResponse(
        style_id=style.id,
        name=localize_field(style, "name", locale) or style.name_en,
        base_price=braider_style.base_price,
        duration_minutes=braider_style.duration_minutes,
    )


def _to_location_response(
    location: BraiderServiceLocation | None,
) -> BraiderLocationResponse | None:
    if location is None:
        return None
    show_exact_address = location.location_type == LocationType.SALON
    return BraiderLocationResponse(
        location_type=location.location_type,
        salon_name=location.salon_name if show_exact_address else None,
        address_line1=location.address_line1 if show_exact_address else None,
        address_line2=location.address_line2 if show_exact_address else None,
        postal_code=location.postal_code if show_exact_address else None,
        city=location.city,
        country=location.country,
        offers_mobile=location.offers_mobile,
        travel_radius_km=location.travel_radius_km,
        travel_fee=location.travel_fee,
    )


async def search_braiders(
    db: AsyncSession,
    *,
    lat: float | None,
    lng: float | None,
    radius_km: float | None,
    style_id: uuid.UUID | None,
    style_slug: str | None,
    search: str | None,
    date_from: date | None,
    date_to: date | None,
    min_amount: Decimal | None,
    max_amount: Decimal | None,
    country_code: str | None,
    is_mobile: bool | None,
    params: PaginationParams,
    locale: str,
) -> PaginatedData[BraiderSearchItemResponse]:
    if (lat is None) != (lng is None):
        raise InvalidSearchLocationError()

    if (date_from is None) != (date_to is None):
        raise InvalidSearchDateRangeError(max_days=_MAX_DATE_RANGE_DAYS)
    if (
        date_from is not None
        and date_to is not None
        and (date_to < date_from or (date_to - date_from).days > _MAX_DATE_RANGE_DAYS)
    ):
        raise InvalidSearchDateRangeError(max_days=_MAX_DATE_RANGE_DAYS)

    if min_amount is not None and max_amount is not None and max_amount < min_amount:
        raise InvalidSearchPriceRangeError()

    resolved_style_id = style_id
    if resolved_style_id is None and style_slug:
        style = await styles_repo.get_style_by_slug(db, style_slug)
        resolved_style_id = style.id if style else uuid.uuid4()  # no match -> empty page

    stmt = discovery_repo.build_search_stmt(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        style_id=resolved_style_id,
        search=search,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        country_code=country_code,
        is_mobile=is_mobile,
    )
    rows, meta = await _paginate_rows(db, stmt, params)

    braider_ids = [row.BraiderProfile.id for row in rows]
    covers = await discovery_repo.list_cover_photos(db, braider_ids)
    offered_styles_by_braider = await discovery_repo.list_offered_styles_for_braiders(
        db, braider_ids
    )

    items = []
    for row in rows:
        profile = row.BraiderProfile
        location = row.BraiderServiceLocation
        cover = covers.get(profile.id)

        matched_style = None
        if resolved_style_id is not None:
            matched_style = _to_matched_style_response(row.BraiderStyle, row.Style, locale)

        # Full menu (capped), so the frontend always has something to show even
        # when the search wasn't filtered to one style (matched_style is null then).
        styles = [
            _to_matched_style_response(braider_style, style, locale)
            for braider_style, style in offered_styles_by_braider.get(profile.id, [])
        ][:_MAX_SEARCH_STYLES]

        items.append(
            BraiderSearchItemResponse(
                id=profile.id,
                business_name=profile.business_name,
                logo_url=storage.build_public_url(profile.logo_object_key)
                if profile.logo_object_key
                else None,
                location=_to_location_response(location),
                distance_km=round(row.distance_km, 2) if row.distance_km is not None else None,
                cover_photo_url=storage.build_public_url(cover.object_key) if cover else None,
                matched_style=matched_style,
                styles=styles,
            )
        )

    return PaginatedData(items=items, pagination=meta)


async def get_braider_detail(
    db: AsyncSession, braider_id: uuid.UUID, *, locale: str
) -> BraiderDetailResponse:
    profile = await discovery_repo.get_visible_profile_by_id(db, braider_id)
    if profile is None:
        raise BraiderNotFoundError()

    location = await service_location_repo.get_by_braider_id(db, profile.id)
    portfolio_images = await portfolio_repo.list_images(db, profile.id)
    offered = await discovery_repo.list_offered_styles(db, profile.id)

    styles_out = []
    for braider_style, style in offered:
        variations = await offerings_repo.list_braider_style_variations(db, braider_style.id)
        addons = await offerings_repo.list_braider_style_addons(db, braider_style.id)
        variation_rows = await discovery_repo.get_style_variations_by_ids(
            db, [v.style_variation_id for v in variations]
        )
        addon_rows = await discovery_repo.get_addons_by_ids(db, [a.addon_id for a in addons])

        styles_out.append(
            BraiderOfferedStyleResponse(
                style_id=style.id,
                slug=style.slug,
                name=localize_field(style, "name", locale) or style.name_en,
                base_price=braider_style.base_price,
                duration_minutes=braider_style.duration_minutes,
                variations=[
                    BraiderStyleVariationPublicResponse(
                        id=v.id,
                        name=(
                            localize_field(variation_rows[v.style_variation_id], "name", locale)
                            or variation_rows[v.style_variation_id].name_en
                        ),
                        price=v.price,
                    )
                    for v in variations
                    if v.style_variation_id in variation_rows
                ],
                addons=[
                    BraiderStyleAddonPublicResponse(
                        id=a.id,
                        name=(
                            localize_field(addon_rows[a.addon_id], "name", locale)
                            or addon_rows[a.addon_id].name_en
                        ),
                        price=a.price,
                        is_required=a.is_required,
                    )
                    for a in addons
                    if a.addon_id in addon_rows
                ],
            )
        )

    return BraiderDetailResponse(
        id=profile.id,
        business_name=profile.business_name,
        logo_url=storage.build_public_url(profile.logo_object_key)
        if profile.logo_object_key
        else None,
        bio=localize_field(profile, "bio", locale),
        gender=profile.gender,
        location=_to_location_response(location),
        portfolio=[
            PortfolioImagePublicResponse(
                id=image.id,
                url=storage.build_public_url(image.object_key),
                caption=localize_field(image, "caption", locale),
                position=image.position,
            )
            for image in portfolio_images
        ],
        styles=styles_out,
    )
