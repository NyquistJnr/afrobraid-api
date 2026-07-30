import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.queue import get_task_queue
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.braiders.portfolio import service
from app.modules.braiders.portfolio.schemas import (
    PortfolioImageConfirmRequest,
    PortfolioImageResponse,
    PortfolioImageUpdateRequest,
    PortfolioImageUploadUrlRequest,
    PortfolioImageUploadUrlResponse,
    PortfolioResponse,
)
from app.modules.users.models import User, UserType

router = APIRouter(
    prefix="/api/v1/braiders/onboarding/portfolio", tags=["Braider Onboarding - Portfolio"]
)

_require_braider = require_roles(UserType.BRAIDER)


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.get(
    "",
    response_model=APIResponse[PortfolioResponse],
    summary="Get your portfolio",
    description=f"`is_complete` becomes true once you have at least "
    f"{service.MIN_PORTFOLIO_IMAGES} photos.",
)
async def get_portfolio(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PortfolioResponse]:
    result = await service.get_portfolio(db, user.id)
    return APIResponse(data=result)


@router.post(
    "/upload-url",
    response_model=APIResponse[PortfolioImageUploadUrlResponse],
    summary="Step 1: get a photo upload URL",
    description=(
        "Returns a presigned URL to PUT the image file directly to storage. "
        "After uploading, call `POST /confirm` with the returned `object_key`."
    ),
)
async def request_upload_url(
    payload: PortfolioImageUploadUrlRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PortfolioImageUploadUrlResponse]:
    result = await service.request_upload_url(db, user.id, data=payload)
    return APIResponse(data=result)


@router.post(
    "/confirm",
    response_model=APIResponse[PortfolioImageResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Step 2: confirm the upload",
    description=(
        "Call this after successfully PUTing the file to the `upload_url` from "
        f"the previous step. Once you have {service.MIN_PORTFOLIO_IMAGES} or more "
        "photos, the PORTFOLIO onboarding step is marked complete automatically. "
        "If you send a `caption`, it's saved in your current locale (`?lang=` or "
        "Accept-Language) and auto-translated into the others."
    ),
)
async def confirm_upload(
    payload: PortfolioImageConfirmRequest,
    request: Request,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[PortfolioImageResponse]:
    result = await service.confirm_upload(
        db, user.id, data=payload, locale=_locale(request), queue=queue
    )
    return APIResponse(data=result)


@router.put(
    "/{image_id}",
    response_model=APIResponse[PortfolioImageResponse],
    summary="Edit a photo's caption",
)
async def update_image(
    image_id: uuid.UUID,
    payload: PortfolioImageUpdateRequest,
    request: Request,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[PortfolioImageResponse]:
    result = await service.update_image(
        db, user.id, image_id, data=payload, locale=_locale(request), queue=queue
    )
    return APIResponse(data=result)


@router.delete(
    "/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a photo",
)
async def delete_image(
    image_id: uuid.UUID,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_image(db, user.id, image_id)
