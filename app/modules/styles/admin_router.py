import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginatedData, PaginationParams
from app.core.queue import get_task_queue
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.styles import service
from app.modules.styles.schemas import (
    AddOnCreateRequest,
    AddOnResponse,
    AddOnUpdateRequest,
    StyleCategoryCreateRequest,
    StyleCategoryResponse,
    StyleCategoryUpdateRequest,
    StyleCreateRequest,
    StyleImageConfirmRequest,
    StyleImageResponse,
    StyleImageUploadUrlRequest,
    StyleImageUploadUrlResponse,
    StyleResponse,
    StyleUpdateRequest,
    StyleVariationCreateRequest,
    StyleVariationResponse,
    StyleVariationUpdateRequest,
)
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/admin", tags=["Admin - Styles"])

_require_admin = require_roles(UserType.ADMIN)


# --- Categories -------------------------------------------------------------


@router.get("/style-categories", response_model=APIResponse[list[StyleCategoryResponse]])
async def list_style_categories(
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[StyleCategoryResponse]]:
    result = await service.list_categories(db)
    return APIResponse(data=result)


@router.post(
    "/style-categories",
    response_model=APIResponse[StyleCategoryResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_style_category(
    payload: StyleCategoryCreateRequest,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[StyleCategoryResponse]:
    result = await service.create_category(db, data=payload, queue=queue)
    return APIResponse(data=result)


@router.put(
    "/style-categories/{category_id}", response_model=APIResponse[StyleCategoryResponse]
)
async def update_style_category(
    category_id: uuid.UUID,
    payload: StyleCategoryUpdateRequest,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[StyleCategoryResponse]:
    result = await service.update_category(db, category_id, data=payload, queue=queue)
    return APIResponse(data=result)


@router.delete("/style-categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_style_category(
    category_id: uuid.UUID,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_category(db, category_id)


# --- Styles -------------------------------------------------------------


@router.get("/styles", response_model=APIResponse[PaginatedData[StyleResponse]])
async def list_styles(
    category_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    params: PaginationParams = Depends(),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedData[StyleResponse]]:
    result = await service.list_styles(
        db, category_id=category_id, search=search, only_active=False, params=params
    )
    return APIResponse(data=result)


@router.get("/styles/{style_id}", response_model=APIResponse[StyleResponse])
async def get_style(
    style_id: uuid.UUID,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[StyleResponse]:
    result = await service.get_style(db, style_id)
    return APIResponse(data=result)


@router.post(
    "/styles", response_model=APIResponse[StyleResponse], status_code=status.HTTP_201_CREATED
)
async def create_style(
    payload: StyleCreateRequest,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[StyleResponse]:
    result = await service.create_style(db, data=payload, created_by=user.id, queue=queue)
    return APIResponse(data=result)


@router.put("/styles/{style_id}", response_model=APIResponse[StyleResponse])
async def update_style(
    style_id: uuid.UUID,
    payload: StyleUpdateRequest,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[StyleResponse]:
    result = await service.update_style(db, style_id, data=payload, queue=queue)
    return APIResponse(data=result)


@router.delete("/styles/{style_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_style(
    style_id: uuid.UUID,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_style(db, style_id)


# --- Style images -------------------------------------------------------


@router.post(
    "/styles/{style_id}/images/upload-url",
    response_model=APIResponse[StyleImageUploadUrlResponse],
)
async def request_style_image_upload_url(
    style_id: uuid.UUID,
    payload: StyleImageUploadUrlRequest,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[StyleImageUploadUrlResponse]:
    result = await service.request_style_image_upload_url(db, style_id, data=payload)
    return APIResponse(data=result)


@router.post(
    "/styles/{style_id}/images/confirm",
    response_model=APIResponse[StyleImageResponse],
    status_code=status.HTTP_201_CREATED,
)
async def confirm_style_image_upload(
    style_id: uuid.UUID,
    payload: StyleImageConfirmRequest,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[StyleImageResponse]:
    result = await service.confirm_style_image_upload(db, style_id, data=payload)
    return APIResponse(data=result)


@router.delete("/styles/{style_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_style_image(
    style_id: uuid.UUID,
    image_id: uuid.UUID,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_style_image(db, style_id, image_id)


# --- Style variations -----------------------------------------------------


@router.post(
    "/styles/{style_id}/variations",
    response_model=APIResponse[StyleVariationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_style_variation(
    style_id: uuid.UUID,
    payload: StyleVariationCreateRequest,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[StyleVariationResponse]:
    result = await service.create_style_variation(db, style_id, data=payload, queue=queue)
    return APIResponse(data=result)


@router.put(
    "/styles/{style_id}/variations/{variation_id}",
    response_model=APIResponse[StyleVariationResponse],
)
async def update_style_variation(
    style_id: uuid.UUID,
    variation_id: uuid.UUID,
    payload: StyleVariationUpdateRequest,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[StyleVariationResponse]:
    result = await service.update_style_variation(
        db, style_id, variation_id, data=payload, queue=queue
    )
    return APIResponse(data=result)


@router.delete(
    "/styles/{style_id}/variations/{variation_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_style_variation(
    style_id: uuid.UUID,
    variation_id: uuid.UUID,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_style_variation(db, style_id, variation_id)


# --- Add-ons ----------------------------------------------------------------


@router.get("/addons", response_model=APIResponse[list[AddOnResponse]])
async def list_addons(
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[AddOnResponse]]:
    result = await service.list_addons(db, only_active=False)
    return APIResponse(data=result)


@router.post(
    "/addons", response_model=APIResponse[AddOnResponse], status_code=status.HTTP_201_CREATED
)
async def create_addon(
    payload: AddOnCreateRequest,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[AddOnResponse]:
    result = await service.create_addon(db, data=payload, queue=queue)
    return APIResponse(data=result)


@router.put("/addons/{addon_id}", response_model=APIResponse[AddOnResponse])
async def update_addon(
    addon_id: uuid.UUID,
    payload: AddOnUpdateRequest,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[AddOnResponse]:
    result = await service.update_addon(db, addon_id, data=payload, queue=queue)
    return APIResponse(data=result)


@router.delete("/addons/{addon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_addon(
    addon_id: uuid.UUID,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_addon(db, addon_id)
