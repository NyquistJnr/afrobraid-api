import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginatedData, PaginationParams
from app.core.response import APIResponse
from app.modules.braiders.discovery import service
from app.modules.braiders.discovery.schemas import BraiderDetailResponse, BraiderSearchItemResponse

router = APIRouter(prefix="/api/v1/braiders", tags=["Braiders - Discovery"])


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.get(
    "",
    response_model=APIResponse[PaginatedData[BraiderSearchItemResponse]],
    summary="Search braiders",
    description=(
        "Public, no auth required. Only returns braiders who've completed "
        "onboarding, payment setup included. Pass `lat`+`lng` together to "
        "sort by distance and optionally filter with `radius_km`. Filter to "
        "braiders offering a specific style with `style_id` or `style_slug` "
        "(if both are given, `style_id` wins). Pass `date_from`+`date_to` "
        "together (max 90 days apart) to only show braiders with at least "
        "one structurally-open day in that range - this doesn't check "
        "bookable slots for a specific style/duration, see "
        "`/braiders/{braider_id}/availability/slots` for that. Filter by "
        "price with `min_amount`/`max_amount` (matches braiders with at "
        "least one offered style priced within the range), by "
        "`country_code` (ISO 3166-1 alpha-2), and by `is_mobile` (braiders "
        "who offer a mobile service at their service location). Each "
        "result's `styles` list is capped at 5 entries."
    ),
)
async def search_braiders(
    request: Request,
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    radius_km: float | None = Query(None, gt=0),
    style_id: uuid.UUID | None = Query(None),
    style_slug: str | None = Query(None),
    search: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    min_amount: Decimal | None = Query(None, ge=0),
    max_amount: Decimal | None = Query(None, ge=0),
    country_code: str | None = Query(None, min_length=2, max_length=2),
    is_mobile: bool | None = Query(None),
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedData[BraiderSearchItemResponse]]:
    result = await service.search_braiders(
        db,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        style_id=style_id,
        style_slug=style_slug,
        search=search,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        country_code=country_code.upper() if country_code else None,
        is_mobile=is_mobile,
        params=params,
        locale=_locale(request),
    )
    return APIResponse(data=result)


@router.get(
    "/{braider_id}",
    response_model=APIResponse[BraiderDetailResponse],
    summary="Get a braider's public profile",
    description="Public, no auth required. 404s if the braider hasn't finished onboarding.",
)
async def get_braider(
    braider_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BraiderDetailResponse]:
    result = await service.get_braider_detail(db, braider_id, locale=_locale(request))
    return APIResponse(data=result)
