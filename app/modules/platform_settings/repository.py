from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform_settings.models import PlatformSettings, SettingValueType


async def get_settings(db: AsyncSession) -> PlatformSettings | None:
    result = await db.execute(select(PlatformSettings).limit(1))
    return result.scalar_one_or_none()


async def create_settings(
    db: AsyncSession,
    *,
    platform_fee_type: SettingValueType,
    platform_fee_value: Decimal,
    vat_type: SettingValueType,
    vat_value: Decimal,
) -> PlatformSettings:
    settings = PlatformSettings(
        platform_fee_type=platform_fee_type,
        platform_fee_value=platform_fee_value,
        vat_type=vat_type,
        vat_value=vat_value,
    )
    db.add(settings)
    await db.flush()
    return settings
