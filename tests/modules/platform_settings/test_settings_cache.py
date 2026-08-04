from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.modules.platform_settings import cache as platform_settings_cache
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token

pytestmark = pytest.mark.asyncio

SETTINGS_URL = "/api/v1/admin/platform-settings"


async def _admin_headers(db_session: AsyncSession) -> dict:
    _, token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    return {"Authorization": f"Bearer {token}"}


async def test_get_effective_settings_populates_cache_on_miss(db_session: AsyncSession):
    redis = get_redis_client()
    try:
        assert await redis.get(platform_settings_cache.PLATFORM_SETTINGS_CACHE_KEY) is None

        effective = await platform_settings_cache.get_effective_settings(db_session, redis)
        assert effective.platform_fee_value == 10
        assert effective.vat_service_value == 20
        assert effective.vat_platform_fee_value == 20
        assert effective.deposit_value == 10

        cached_raw = await redis.get(platform_settings_cache.PLATFORM_SETTINGS_CACHE_KEY)
        assert cached_raw is not None
    finally:
        await redis.aclose()


async def test_get_effective_settings_hits_cache_without_extra_db_write(
    db_session: AsyncSession,
):
    redis = get_redis_client()
    try:
        first = await platform_settings_cache.get_effective_settings(db_session, redis)
        # Tamper with the cached payload directly so a second call can only
        # be returning this (proving it read the cache, not the DB).
        await redis.set(
            platform_settings_cache.PLATFORM_SETTINGS_CACHE_KEY,
            '{"platform_fee_type": "FIXED", "platform_fee_value": "999.00", '
            '"vat_service_type": "PERCENTAGE", "vat_service_value": "20", '
            '"vat_platform_fee_type": "PERCENTAGE", "vat_platform_fee_value": "20", '
            '"deposit_type": "PERCENTAGE", "deposit_value": "10"}',
        )
        second = await platform_settings_cache.get_effective_settings(db_session, redis)
        assert second.platform_fee_value != first.platform_fee_value
        assert second.platform_fee_value == 999
    finally:
        await redis.aclose()


async def test_cache_ttl_is_at_least_24_hours():
    assert platform_settings_cache.PLATFORM_SETTINGS_CACHE_TTL_SECONDS >= 60 * 60 * 24


async def test_patch_invalidates_cache(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(db_session)
    redis = get_redis_client()
    try:
        # Warm the cache with the seeded default.
        cached = await platform_settings_cache.get_effective_settings(db_session, redis)
        assert cached.platform_fee_value == 10

        resp = await client.patch(
            SETTINGS_URL, json={"platform_fee_value": "12.50"}, headers=headers
        )
        assert resp.status_code == 200, resp.text

        # The cache must have been invalidated by the PATCH - a fresh read
        # picks up the new value rather than the stale cached 10.
        refreshed = await platform_settings_cache.get_effective_settings(db_session, redis)
        assert refreshed.platform_fee_value == Decimal("12.50")
    finally:
        await redis.aclose()
