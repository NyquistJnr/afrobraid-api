import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginatedData, PaginationParams
from app.core.response import APIResponse
from app.modules.auth.dependencies import get_current_user
from app.modules.styles import service
from app.modules.styles.schemas import AddOnResponse, StyleCategoryResponse, StyleResponse
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1", tags=["Styles"])


@router.get("/style-categories", response_model=APIResponse[list[StyleCategoryResponse]])
async def list_style_categories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[StyleCategoryResponse]]:
    result = await service.list_categories(db)
    return APIResponse(data=result)


@router.get("/styles", response_model=APIResponse[PaginatedData[StyleResponse]])
async def list_styles(
    category_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    params: PaginationParams = Depends(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedData[StyleResponse]]:
    result = await service.list_styles(
        db, category_id=category_id, search=search, only_active=True, params=params
    )
    return APIResponse(data=result)


@router.get("/styles/{style_id}", response_model=APIResponse[StyleResponse])
async def get_style(
    style_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[StyleResponse]:
    result = await service.get_style(db, style_id)
    return APIResponse(data=result)


@router.get("/addons", response_model=APIResponse[list[AddOnResponse]])
async def list_addons(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[AddOnResponse]]:
    result = await service.list_addons(db, only_active=True)
    return APIResponse(data=result)
