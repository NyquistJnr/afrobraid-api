import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginatedData, PaginationParams
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.braiders.offerings import service
from app.modules.braiders.offerings.schemas import (
    BraiderStyleCreateRequest,
    BraiderStyleResponse,
    BraiderStyleUpdateRequest,
)
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/braiders/onboarding/services", tags=["Braider Onboarding - Services"])

_require_braider = require_roles(UserType.BRAIDER)


@router.get(
    "",
    response_model=APIResponse[PaginatedData[BraiderStyleResponse]],
    summary="List your service menu",
)
async def list_braider_styles(
    params: PaginationParams = Depends(),
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedData[BraiderStyleResponse]]:
    result = await service.list_braider_styles(db, user.id, params=params)
    return APIResponse(data=result)


@router.get(
    "/{braider_style_id}",
    response_model=APIResponse[BraiderStyleResponse],
    summary="Get a style from your menu",
    description=(
        "`braider_style_id` is the `id` field from an entry in the list above "
        "(not the catalog `style_id`)."
    ),
)
async def get_braider_style(
    braider_style_id: uuid.UUID,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BraiderStyleResponse]:
    result = await service.get_braider_style(db, user.id, braider_style_id)
    return APIResponse(data=result)


@router.post(
    "",
    response_model=APIResponse[BraiderStyleResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a style to your menu",
    description=(
        "Before calling this, get real IDs to test with:\n\n"
        "1. `GET /api/v1/styles` for a `style_id` (and, if it has any, "
        "`variations[].id` for `style_variation_id`).\n"
        "2. `GET /api/v1/addons` for an `addon_id`.\n\n"
        "`variations` and `addons` are each a list of **objects**, not a list "
        'of ID strings - e.g. `[{"style_variation_id": "...", "price": "20.00"}]`, '
        'not `["<uuid>"]`. Both default to `[]` and can be omitted entirely if '
        "this style has no variations or add-ons you want to offer."
    ),
)
async def create_braider_style(
    payload: BraiderStyleCreateRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BraiderStyleResponse]:
    result = await service.create_braider_style(db, user.id, data=payload)
    return APIResponse(data=result)


@router.put(
    "/{braider_style_id}",
    response_model=APIResponse[BraiderStyleResponse],
    summary="Edit a style already on your menu",
    description=(
        "`braider_style_id` is the `id` field from this style's entry in "
        "`GET /api/v1/braiders/onboarding/services` (not the catalog `style_id`). "
        "Only send the fields you want to change. If you send `variations` or "
        "`addons`, that list fully replaces the existing one - include every "
        "entry you still want, not just the new ones."
    ),
)
async def update_braider_style(
    braider_style_id: uuid.UUID,
    payload: BraiderStyleUpdateRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BraiderStyleResponse]:
    result = await service.update_braider_style(db, user.id, braider_style_id, data=payload)
    return APIResponse(data=result)


@router.delete(
    "/{braider_style_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a style from your menu",
    description=(
        "`braider_style_id` is the `id` field from this style's entry in "
        "`GET /api/v1/braiders/onboarding/services` (not the catalog `style_id`)."
    ),
)
async def delete_braider_style(
    braider_style_id: uuid.UUID,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_braider_style(db, user.id, braider_style_id)
