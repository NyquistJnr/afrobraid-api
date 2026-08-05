from fastapi import APIRouter, Depends, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.platform_settings import service
from app.modules.platform_settings.schemas import (
    CountryVatSettingsResponse,
    CountryVatSettingsUpsertRequest,
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


@router.get("/country-vat", response_model=APIResponse[list[CountryVatSettingsResponse]])
async def list_country_vat_settings(
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[CountryVatSettingsResponse]]:
    result = await service.list_country_vat_settings(db)
    return APIResponse(data=result)


@router.put("/country-vat/{country}", response_model=APIResponse[CountryVatSettingsResponse])
async def upsert_country_vat_settings(
    country: str,
    payload: CountryVatSettingsUpsertRequest,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> APIResponse[CountryVatSettingsResponse]:
    result = await service.upsert_country_vat_settings(db, redis, country=country, data=payload)
    return APIResponse(data=result)


@router.delete("/country-vat/{country}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_country_vat_settings(
    country: str,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> None:
    await service.delete_country_vat_settings(db, redis, country=country)
