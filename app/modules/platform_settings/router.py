from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.platform_settings import service
from app.modules.platform_settings.schemas import (
    PlatformSettingsResponse,
    PlatformSettingsUpdateRequest,
)
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/admin/platform-settings", tags=["Admin - Platform Settings"])

_require_admin = require_roles(UserType.ADMIN)


@router.get("", response_model=APIResponse[PlatformSettingsResponse])
async def get_platform_settings(
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PlatformSettingsResponse]:
    result = await service.get_settings(db)
    return APIResponse(data=result)


@router.patch("", response_model=APIResponse[PlatformSettingsResponse])
async def update_platform_settings(
    payload: PlatformSettingsUpdateRequest,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> APIResponse[PlatformSettingsResponse]:
    result = await service.update_settings(db, redis, data=payload)
    return APIResponse(data=result)
