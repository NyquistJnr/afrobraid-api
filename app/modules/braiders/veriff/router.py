from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.braiders.veriff import service
from app.modules.braiders.veriff.schemas import StartVerificationResponse, VeriffStatusResponse
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/braiders/onboarding/veriff", tags=["Braider Onboarding - Veriff"])

_require_braider = require_roles(UserType.BRAIDER)


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.post("/session", response_model=APIResponse[StartVerificationResponse])
async def start_verification(
    request: Request,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> APIResponse[StartVerificationResponse]:
    result = await service.start_verification(db, redis, user, locale=_locale(request))
    return APIResponse(data=result)


@router.get("/status", response_model=APIResponse[VeriffStatusResponse])
async def get_status(
    request: Request,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[VeriffStatusResponse]:
    result = await service.get_status(db, user.id, locale=_locale(request))
    return APIResponse(data=result)


@router.post("/refresh", response_model=APIResponse[VeriffStatusResponse])
async def refresh_status(
    request: Request,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[VeriffStatusResponse]:
    result = await service.refresh_status(db, user.id, locale=_locale(request))
    return APIResponse(data=result)
