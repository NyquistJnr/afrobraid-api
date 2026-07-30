from arq import ArqRedis
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.queue import get_task_queue
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.braiders import service
from app.modules.braiders.schemas import (
    BusinessInfoResponse,
    BusinessInfoUpdateRequest,
    LogoConfirmRequest,
    LogoUploadUrlRequest,
    LogoUploadUrlResponse,
    OnboardingStatusResponse,
)
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/braiders/onboarding", tags=["Braider Onboarding"])

_require_braider = require_roles(UserType.BRAIDER)


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.get("/status", response_model=APIResponse[OnboardingStatusResponse])
async def get_onboarding_status(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[OnboardingStatusResponse]:
    result = await service.get_onboarding_status(db, user.id)
    return APIResponse(data=result)


@router.get("/business-info", response_model=APIResponse[BusinessInfoResponse])
async def get_business_info(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BusinessInfoResponse]:
    result = await service.get_business_info(db, user.id)
    return APIResponse(data=result)


@router.put("/business-info", response_model=APIResponse[BusinessInfoResponse])
async def update_business_info(
    payload: BusinessInfoUpdateRequest,
    request: Request,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[BusinessInfoResponse]:
    result = await service.update_business_info(
        db, user.id, data=payload, locale=_locale(request), queue=queue
    )
    return APIResponse(data=result)


@router.post("/business-info/logo/upload-url", response_model=APIResponse[LogoUploadUrlResponse])
async def request_logo_upload_url(
    payload: LogoUploadUrlRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[LogoUploadUrlResponse]:
    result = await service.request_logo_upload_url(db, user.id, data=payload)
    return APIResponse(data=result)


@router.post("/business-info/logo/confirm", response_model=APIResponse[BusinessInfoResponse])
async def confirm_logo_upload(
    payload: LogoConfirmRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BusinessInfoResponse]:
    result = await service.confirm_logo_upload(db, user.id, data=payload)
    return APIResponse(data=result)
