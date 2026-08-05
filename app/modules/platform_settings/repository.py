from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform_settings.models import (
    CountryVatSettings,
    PlatformSettings,
    SettingValueType,
)


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
    vat_platform_fee_type: SettingValueType,
    vat_platform_fee_value: Decimal,
    deposit_type: SettingValueType,
    deposit_value: Decimal,
) -> PlatformSettings:
    settings = PlatformSettings(
        platform_fee_type=platform_fee_type,
        platform_fee_value=platform_fee_value,
        vat_type=vat_type,
        vat_value=vat_value,
        vat_platform_fee_type=vat_platform_fee_type,
        vat_platform_fee_value=vat_platform_fee_value,
        deposit_type=deposit_type,
        deposit_value=deposit_value,
    )
    db.add(settings)
    await db.flush()
    return settings


async def get_country_vat_settings(db: AsyncSession, country: str) -> CountryVatSettings | None:
    result = await db.execute(
        select(CountryVatSettings).where(CountryVatSettings.country == country)
    )
    return result.scalar_one_or_none()


async def list_country_vat_settings(db: AsyncSession) -> list[CountryVatSettings]:
    result = await db.execute(select(CountryVatSettings).order_by(CountryVatSettings.country))
    return list(result.scalars().all())


async def upsert_country_vat_settings(
    db: AsyncSession,
    *,
    country: str,
    vat_type: SettingValueType,
    vat_value: Decimal,
    vat_platform_fee_type: SettingValueType,
    vat_platform_fee_value: Decimal,
) -> CountryVatSettings:
    existing = await get_country_vat_settings(db, country)
    if existing is not None:
        existing.vat_type = vat_type
        existing.vat_value = vat_value
        existing.vat_platform_fee_type = vat_platform_fee_type
        existing.vat_platform_fee_value = vat_platform_fee_value
        await db.flush()
        return existing

    row = CountryVatSettings(
        country=country,
        vat_type=vat_type,
        vat_value=vat_value,
        vat_platform_fee_type=vat_platform_fee_type,
        vat_platform_fee_value=vat_platform_fee_value,
    )
    db.add(row)
    await db.flush()
    return row


async def delete_country_vat_settings(db: AsyncSession, row: CountryVatSettings) -> None:
    await db.execute(delete(CountryVatSettings).where(CountryVatSettings.id == row.id))
    await db.flush()

