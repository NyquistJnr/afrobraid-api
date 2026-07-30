from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.modules.auth.dependencies import require_roles
from app.modules.braiders.veriff import service
from app.modules.braiders.veriff.schemas import StartVerificationResponse, VeriffStatusResponse
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/braiders/onboarding/veriff", tags=["Braider Onboarding - Veriff"])

_require_braider = require_roles(UserType.BRAIDER)


@router.post("/session", response_model=StartVerificationResponse)
async def start_verification(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> StartVerificationResponse:
    return await service.start_verification(db, redis, user)


@router.get("/status", response_model=VeriffStatusResponse)
async def get_status(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> VeriffStatusResponse:
    return await service.get_status(db, user.id)


@router.post("/refresh", response_model=VeriffStatusResponse)
async def refresh_status(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> VeriffStatusResponse:
    return await service.refresh_status(db, user.id)
