from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.braiders.phone_verification import service
from app.modules.braiders.phone_verification.schemas import (
    PhoneVerificationStatusResponse,
    SendCodeRequest,
    SendCodeResponse,
    VerifyCodeRequest,
    VerifyCodeResponse,
)
from app.modules.users.models import User, UserType

router = APIRouter(
    prefix="/api/v1/braiders/onboarding/phone-verification",
    tags=["Braider Onboarding - Phone Verification"],
)

_require_braider = require_roles(UserType.BRAIDER)


@router.post("/send-code", response_model=APIResponse[SendCodeResponse])
async def send_code(
    payload: SendCodeRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> APIResponse[SendCodeResponse]:
    result = await service.send_code(db, redis, user, data=payload)
    return APIResponse(data=result)


@router.post("/verify-code", response_model=APIResponse[VerifyCodeResponse])
async def verify_code(
    payload: VerifyCodeRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[VerifyCodeResponse]:
    result = await service.verify_code(db, user, data=payload)
    return APIResponse(data=result)


@router.get("/status", response_model=APIResponse[PhoneVerificationStatusResponse])
async def get_status(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PhoneVerificationStatusResponse]:
    result = await service.get_status(db, user)
    return APIResponse(data=result)
