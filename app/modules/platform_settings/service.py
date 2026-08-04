from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidSettingValueError
from app.modules.platform_settings import repository as platform_settings_repo
from app.modules.platform_settings.models import PlatformSettings, SettingValueType
from app.modules.platform_settings.schemas import (
    PlatformSettingsResponse,
    PlatformSettingsUpdateRequest,
)

_DEFAULT_PLATFORM_FEE_TYPE = SettingValueType.PERCENTAGE
_DEFAULT_PLATFORM_FEE_VALUE = Decimal("10.00")
_DEFAULT_VAT_TYPE = SettingValueType.PERCENTAGE
_DEFAULT_VAT_VALUE = Decimal("20.00")


async def _get_or_create_settings(db: AsyncSession) -> PlatformSettings:
    settings = await platform_settings_repo.get_settings(db)
    if settings is None:
        settings = await platform_settings_repo.create_settings(
            db,
            platform_fee_type=_DEFAULT_PLATFORM_FEE_TYPE,
            platform_fee_value=_DEFAULT_PLATFORM_FEE_VALUE,
            vat_type=_DEFAULT_VAT_TYPE,
            vat_value=_DEFAULT_VAT_VALUE,
        )
    return settings


def _validate_percentage_bounds(settings: PlatformSettings) -> None:
    if settings.platform_fee_type == SettingValueType.PERCENTAGE and settings.platform_fee_value > 100:
        raise InvalidSettingValueError()
    if settings.vat_type == SettingValueType.PERCENTAGE and settings.vat_value > 100:
        raise InvalidSettingValueError()


def _to_response(settings: PlatformSettings) -> PlatformSettingsResponse:
    return PlatformSettingsResponse(
        id=settings.id,
        platform_fee_type=settings.platform_fee_type,
        platform_fee_value=settings.platform_fee_value,
        vat_type=settings.vat_type,
        vat_value=settings.vat_value,
    )


async def get_settings(db: AsyncSession) -> PlatformSettingsResponse:
    settings = await _get_or_create_settings(db)
    await db.commit()
    return _to_response(settings)


async def update_settings(
    db: AsyncSession, *, data: PlatformSettingsUpdateRequest
) -> PlatformSettingsResponse:
    settings = await _get_or_create_settings(db)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(settings, field, value)

    _validate_percentage_bounds(settings)

    await db.commit()
    return _to_response(settings)
