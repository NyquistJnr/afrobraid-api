from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CountryVatSettingsNotFoundError,
    InvalidCountryCodeError,
    InvalidSettingValueError,
)
from app.modules.platform_settings import cache as platform_settings_cache
from app.modules.platform_settings import repository as platform_settings_repo
from app.modules.platform_settings.models import (
    CountryVatSettings,
    PlatformSettings,
    SettingValueType,
)
from app.modules.platform_settings.schemas import (
    CountryVatSettingsResponse,
    CountryVatSettingsUpsertRequest,
    PlatformSettingsResponse,
    PlatformSettingsUpdateRequest,
)

_DEFAULT_PLATFORM_FEE_TYPE = SettingValueType.PERCENTAGE
_DEFAULT_PLATFORM_FEE_VALUE = Decimal("10.00")
_DEFAULT_VAT_TYPE = SettingValueType.PERCENTAGE
_DEFAULT_VAT_VALUE = Decimal("20.00")
# Seeded equal to _DEFAULT_VAT_VALUE - the platform fee is its own taxable
# supply with an independently configurable rate, but starts at the same
# 20% so the initially-approved pricing example reproduces exactly.
_DEFAULT_VAT_PLATFORM_FEE_TYPE = SettingValueType.PERCENTAGE
_DEFAULT_VAT_PLATFORM_FEE_VALUE = Decimal("20.00")
_DEFAULT_DEPOSIT_TYPE = SettingValueType.PERCENTAGE
_DEFAULT_DEPOSIT_VALUE = Decimal("10.00")


async def _get_or_create_settings(db: AsyncSession) -> PlatformSettings:
    settings = await platform_settings_repo.get_settings(db)
    if settings is None:
        settings = await platform_settings_repo.create_settings(
            db,
            platform_fee_type=_DEFAULT_PLATFORM_FEE_TYPE,
            platform_fee_value=_DEFAULT_PLATFORM_FEE_VALUE,
            vat_type=_DEFAULT_VAT_TYPE,
            vat_value=_DEFAULT_VAT_VALUE,
            vat_platform_fee_type=_DEFAULT_VAT_PLATFORM_FEE_TYPE,
            vat_platform_fee_value=_DEFAULT_VAT_PLATFORM_FEE_VALUE,
            deposit_type=_DEFAULT_DEPOSIT_TYPE,
            deposit_value=_DEFAULT_DEPOSIT_VALUE,
        )
    return settings


def _validate_percentage_bounds(settings: PlatformSettings) -> None:
    checks = (
        (settings.platform_fee_type, settings.platform_fee_value),
        (settings.vat_type, settings.vat_value),
        (settings.vat_platform_fee_type, settings.vat_platform_fee_value),
        (settings.deposit_type, settings.deposit_value),
    )
    for value_type, value in checks:
        if value_type == SettingValueType.PERCENTAGE and value > 100:
            raise InvalidSettingValueError()


def _to_response(settings: PlatformSettings) -> PlatformSettingsResponse:
    return PlatformSettingsResponse(
        id=settings.id,
        platform_fee_type=settings.platform_fee_type,
        platform_fee_value=settings.platform_fee_value,
        vat_type=settings.vat_type,
        vat_value=settings.vat_value,
        vat_platform_fee_type=settings.vat_platform_fee_type,
        vat_platform_fee_value=settings.vat_platform_fee_value,
        deposit_type=settings.deposit_type,
        deposit_value=settings.deposit_value,
    )


async def get_settings(db: AsyncSession) -> PlatformSettingsResponse:
    """Admin-facing read - always hits the DB directly, never the cache, so
    an admin is never shown a value staler than their own last write."""
    settings = await _get_or_create_settings(db)
    await db.commit()
    return _to_response(settings)


async def update_settings(
    db: AsyncSession, redis: Redis, *, data: PlatformSettingsUpdateRequest
) -> PlatformSettingsResponse:
    settings = await _get_or_create_settings(db)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(settings, field, value)

    _validate_percentage_bounds(settings)

    # Double-delete around the commit: a read that races this write and
    # repopulates the cache from the pre-commit snapshot gets flushed out
    # again by the second delete, rather than pinning a stale value for the
    # full 7-day TTL.
    await platform_settings_cache.invalidate(redis)
    await db.commit()
    await platform_settings_cache.invalidate(redis)

    return _to_response(settings)


def _normalize_country(country: str) -> str:
    country = country.strip()
    if len(country) != 2 or not country.isalpha():
        raise InvalidCountryCodeError()
    return country.upper()


def _validate_country_vat_percentage_bounds(data: CountryVatSettingsUpsertRequest) -> None:
    checks = (
        (data.vat_type, data.vat_value),
        (data.vat_platform_fee_type, data.vat_platform_fee_value),
    )
    for value_type, value in checks:
        if value_type == SettingValueType.PERCENTAGE and value > 100:
            raise InvalidSettingValueError()


def _to_country_vat_response(row: CountryVatSettings) -> CountryVatSettingsResponse:
    return CountryVatSettingsResponse(
        country=row.country,
        vat_type=row.vat_type,
        vat_value=row.vat_value,
        vat_platform_fee_type=row.vat_platform_fee_type,
        vat_platform_fee_value=row.vat_platform_fee_value,
    )


async def list_country_vat_settings(db: AsyncSession) -> list[CountryVatSettingsResponse]:
    """Admin-facing read - always hits the DB directly, same as get_settings."""
    rows = await platform_settings_repo.list_country_vat_settings(db)
    return [_to_country_vat_response(row) for row in rows]


async def upsert_country_vat_settings(
    db: AsyncSession, redis: Redis, *, country: str, data: CountryVatSettingsUpsertRequest
) -> CountryVatSettingsResponse:
    normalized = _normalize_country(country)
    _validate_country_vat_percentage_bounds(data)

    row = await platform_settings_repo.upsert_country_vat_settings(
        db,
        country=normalized,
        vat_type=data.vat_type,
        vat_value=data.vat_value,
        vat_platform_fee_type=data.vat_platform_fee_type,
        vat_platform_fee_value=data.vat_platform_fee_value,
    )

    # Same double-delete-around-commit shape as update_settings, scoped to
    # just this country's cache key.
    await platform_settings_cache.invalidate_country(redis, normalized)
    await db.commit()
    await platform_settings_cache.invalidate_country(redis, normalized)

    return _to_country_vat_response(row)


async def delete_country_vat_settings(db: AsyncSession, redis: Redis, *, country: str) -> None:
    normalized = _normalize_country(country)
    row = await platform_settings_repo.get_country_vat_settings(db, normalized)
    if row is None:
        raise CountryVatSettingsNotFoundError()

    await platform_settings_repo.delete_country_vat_settings(db, row)

    await platform_settings_cache.invalidate_country(redis, normalized)
    await db.commit()
    await platform_settings_cache.invalidate_country(redis, normalized)
