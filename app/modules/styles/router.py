import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginatedData, PaginationParams
from app.core.response import APIResponse
from app.modules.styles import service
from app.modules.styles.schemas import (
    AddOnPublicResponse,
    StyleCategoryPublicResponse,
    StylePublicResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Styles"])


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.get("/style-categories", response_model=APIResponse[list[StyleCategoryPublicResponse]])
async def list_style_categories(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[StyleCategoryPublicResponse]]:
    result = await service.list_categories_public(db, locale=_locale(request))
    return APIResponse(data=result)


@router.get("/styles", response_model=APIResponse[PaginatedData[StylePublicResponse]])
async def list_styles(
    request: Request,
    category_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedData[StylePublicResponse]]:
    result = await service.list_styles_public(
        db,
        category_id=category_id,
        search=search,
        only_active=True,
        params=params,
        locale=_locale(request),
    )
    return APIResponse(data=result)


@router.get("/styles/{style_id}", response_model=APIResponse[StylePublicResponse])
async def get_style(
    style_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[StylePublicResponse]:
    result = await service.get_style_public(db, style_id, locale=_locale(request))
    return APIResponse(data=result)


@router.get("/addons", response_model=APIResponse[list[AddOnPublicResponse]])
async def list_addons(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[AddOnPublicResponse]]:
    result = await service.list_addons_public(db, only_active=True, locale=_locale(request))
    return APIResponse(data=result)
