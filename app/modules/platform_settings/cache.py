"""Redis-backed read path for `PlatformSettings`, used by anything that
needs the fee/VAT/deposit configuration on a hot path (chiefly the booking
pricing engine) without hitting Postgres on every request.

TTL is 7 days - comfortably over the "cache at least 24 hours" requirement.
`update_settings` double-deletes the key around its commit (delete -> commit
-> delete again) so a read racing the write can't repopulate the cache from
the pre-commit snapshot. The admin GET/PATCH endpoints always read the DB
directly - only `get_effective_settings` goes through this cache, so an
admin can never be shown a stale value for their own change.
"""

from dataclasses import dataclass
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import delete, get_json, set_json
from app.modules.platform_settings import repository as platform_settings_repo
from app.modules.platform_settings.models import SettingValueType

PLATFORM_SETTINGS_CACHE_KEY = "cache:platform_settings:v1"
PLATFORM_SETTINGS_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


@dataclass(frozen=True)
class EffectivePlatformSettings:
    """A point-in-time snapshot of the platform's fee/VAT/deposit knobs.
    Each setting keeps its own type+value pair (not a bare rate) because
    every one of them - fee, VAT-on-service, VAT-on-platform-fee, deposit -
    can independently be PERCENTAGE or FIXED."""

    platform_fee_type: SettingValueType
    platform_fee_value: Decimal
    vat_service_type: SettingValueType
    vat_service_value: Decimal
    vat_platform_fee_type: SettingValueType
    vat_platform_fee_value: Decimal
    deposit_type: SettingValueType
    deposit_value: Decimal


def _to_cache_payload(settings: EffectivePlatformSettings) -> dict:
    return {
        "platform_fee_type": settings.platform_fee_type.value,
        "platform_fee_value": str(settings.platform_fee_value),
        "vat_service_type": settings.vat_service_type.value,
        "vat_service_value": str(settings.vat_service_value),
        "vat_platform_fee_type": settings.vat_platform_fee_type.value,
        "vat_platform_fee_value": str(settings.vat_platform_fee_value),
        "deposit_type": settings.deposit_type.value,
        "deposit_value": str(settings.deposit_value),
    }


def _from_cache_payload(payload: dict) -> EffectivePlatformSettings:
    return EffectivePlatformSettings(
        platform_fee_type=SettingValueType(payload["platform_fee_type"]),
        platform_fee_value=Decimal(payload["platform_fee_value"]),
        vat_service_type=SettingValueType(payload["vat_service_type"]),
        vat_service_value=Decimal(payload["vat_service_value"]),
        vat_platform_fee_type=SettingValueType(payload["vat_platform_fee_type"]),
        vat_platform_fee_value=Decimal(payload["vat_platform_fee_value"]),
        deposit_type=SettingValueType(payload["deposit_type"]),
        deposit_value=Decimal(payload["deposit_value"]),
    )


async def get_effective_settings(
    db: AsyncSession, redis: Redis, country: str | None = None
) -> EffectivePlatformSettings:
    cache_key = PLATFORM_SETTINGS_CACHE_KEY
    if country is not None:
        cache_key = f"{PLATFORM_SETTINGS_CACHE_KEY}:country:{country}"

    cached = await get_json(redis, cache_key)
    if cached is not None:
        return _from_cache_payload(cached)

    # Deliberately does not call platform_settings.service._get_or_create_settings
    # to avoid a service<->cache import cycle; the settings row is expected to
    # already exist by the time anything is pricing a booking (the admin GET/PATCH
    # endpoints, or this module's own service, create it lazily on first touch).
    settings = await platform_settings_repo.get_settings(db)
    if settings is None:
        from app.modules.platform_settings import service as platform_settings_service

        settings = await platform_settings_service._get_or_create_settings(db)
        await db.commit()

    vat_service_type = settings.vat_type
    vat_service_value = settings.vat_value
    vat_platform_fee_type = settings.vat_platform_fee_type
    vat_platform_fee_value = settings.vat_platform_fee_value

    if country is not None:
        country_override = await platform_settings_repo.get_country_vat_settings(db, country)
        if country_override is not None:
            vat_service_type = country_override.vat_type
            vat_service_value = country_override.vat_value
            vat_platform_fee_type = country_override.vat_platform_fee_type
            vat_platform_fee_value = country_override.vat_platform_fee_value

    effective = EffectivePlatformSettings(
        platform_fee_type=settings.platform_fee_type,
        platform_fee_value=settings.platform_fee_value,
        vat_service_type=vat_service_type,
        vat_service_value=vat_service_value,
        vat_platform_fee_type=vat_platform_fee_type,
        vat_platform_fee_value=vat_platform_fee_value,
        deposit_type=settings.deposit_type,
        deposit_value=settings.deposit_value,
    )
    await set_json(
        redis,
        cache_key,
        _to_cache_payload(effective),
        ttl_seconds=PLATFORM_SETTINGS_CACHE_TTL_SECONDS,
    )
    return effective


async def invalidate(redis: Redis) -> None:
    await delete(redis, PLATFORM_SETTINGS_CACHE_KEY)
