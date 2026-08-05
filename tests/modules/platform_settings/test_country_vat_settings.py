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
COUNTRY_VAT_URL = f"{SETTINGS_URL}/country-vat"


async def _admin_headers(db_session: AsyncSession) -> dict:
    _, token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    return {"Authorization": f"Bearer {token}"}


def _payload(vat_value: str = "19.00", fee_value: str = "19.00") -> dict:
    return {
        "vat_type": "PERCENTAGE",
        "vat_value": vat_value,
        "vat_platform_fee_type": "PERCENTAGE",
        "vat_platform_fee_value": fee_value,
    }


async def test_upsert_creates_new_country_override(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(db_session)

    resp = await client.put(f"{COUNTRY_VAT_URL}/DE", json=_payload(), headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["country"] == "DE"
    assert data["vat_value"] == "19.00"
    assert data["vat_platform_fee_value"] == "19.00"

    list_resp = await client.get(COUNTRY_VAT_URL, headers=headers)
    countries = {row["country"] for row in list_resp.json()["data"]}
    assert "DE" in countries


async def test_upsert_updates_existing_country_override(
    client: AsyncClient, db_session: AsyncSession
):
    headers = await _admin_headers(db_session)

    await client.put(f"{COUNTRY_VAT_URL}/DE", json=_payload("19.00"), headers=headers)
    resp = await client.put(f"{COUNTRY_VAT_URL}/DE", json=_payload("21.00"), headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["vat_value"] == "21.00"

    list_resp = await client.get(COUNTRY_VAT_URL, headers=headers)
    de_rows = [row for row in list_resp.json()["data"] if row["country"] == "DE"]
    assert len(de_rows) == 1
    assert de_rows[0]["vat_value"] == "21.00"


async def test_upsert_normalizes_country_case(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(db_session)

    resp = await client.put(f"{COUNTRY_VAT_URL}/de", json=_payload(), headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["country"] == "DE"


async def test_upsert_rejects_invalid_country_code(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(db_session)

    resp = await client.put(f"{COUNTRY_VAT_URL}/GER", json=_payload(), headers=headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_COUNTRY_CODE"


async def test_upsert_rejects_percentage_over_100(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(db_session)

    resp = await client.put(f"{COUNTRY_VAT_URL}/DE", json=_payload("150.00"), headers=headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SETTING_VALUE"


async def test_delete_removes_override(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(db_session)

    await client.put(f"{COUNTRY_VAT_URL}/DE", json=_payload(), headers=headers)
    resp = await client.delete(f"{COUNTRY_VAT_URL}/DE", headers=headers)
    assert resp.status_code == 204

    list_resp = await client.get(COUNTRY_VAT_URL, headers=headers)
    countries = {row["country"] for row in list_resp.json()["data"]}
    assert "DE" not in countries


async def test_delete_unknown_country_404(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(db_session)

    resp = await client.delete(f"{COUNTRY_VAT_URL}/NG", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "COUNTRY_VAT_SETTINGS_NOT_FOUND"


async def test_non_admin_cannot_access_country_vat(client: AsyncClient, db_session: AsyncSession):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(COUNTRY_VAT_URL, headers=headers)
    assert resp.status_code == 403

    resp = await client.put(f"{COUNTRY_VAT_URL}/DE", json=_payload(), headers=headers)
    assert resp.status_code == 403


async def test_effective_settings_falls_back_to_global_for_unlisted_country(
    db_session: AsyncSession,
):
    redis = get_redis_client()
    try:
        effective = await platform_settings_cache.get_effective_settings(
            db_session, redis, country="NG"
        )
        assert effective.vat_service_value == 20
        assert effective.vat_platform_fee_value == 20
    finally:
        await redis.aclose()


async def test_effective_settings_applies_country_override(
    client: AsyncClient, db_session: AsyncSession
):
    headers = await _admin_headers(db_session)
    await client.put(f"{COUNTRY_VAT_URL}/DE", json=_payload("19.00", "19.00"), headers=headers)

    redis = get_redis_client()
    try:
        effective = await platform_settings_cache.get_effective_settings(
            db_session, redis, country="DE"
        )
        assert effective.vat_service_value == Decimal("19.00")
        assert effective.vat_platform_fee_value == Decimal("19.00")
        # Platform fee itself is never country-specific.
        assert effective.platform_fee_value == 10

        cached_raw = await redis.get("cache:platform_settings:v1:country:DE")
        assert cached_raw is not None
    finally:
        await redis.aclose()


async def test_country_upsert_invalidates_country_cache(
    client: AsyncClient, db_session: AsyncSession
):
    headers = await _admin_headers(db_session)
    redis = get_redis_client()
    try:
        await client.put(f"{COUNTRY_VAT_URL}/DE", json=_payload("19.00"), headers=headers)
        warm = await platform_settings_cache.get_effective_settings(
            db_session, redis, country="DE"
        )
        assert warm.vat_service_value == Decimal("19.00")

        resp = await client.put(f"{COUNTRY_VAT_URL}/DE", json=_payload("21.00"), headers=headers)
        assert resp.status_code == 200, resp.text

        refreshed = await platform_settings_cache.get_effective_settings(
            db_session, redis, country="DE"
        )
        assert refreshed.vat_service_value == Decimal("21.00")
    finally:
        await redis.aclose()


async def test_country_delete_invalidates_cache(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(db_session)
    redis = get_redis_client()
    try:
        await client.put(f"{COUNTRY_VAT_URL}/DE", json=_payload("19.00"), headers=headers)
        warm = await platform_settings_cache.get_effective_settings(
            db_session, redis, country="DE"
        )
        assert warm.vat_service_value == Decimal("19.00")

        resp = await client.delete(f"{COUNTRY_VAT_URL}/DE", headers=headers)
        assert resp.status_code == 204

        # No override left - falls back to the global 20% rate again.
        refreshed = await platform_settings_cache.get_effective_settings(
            db_session, redis, country="DE"
        )
        assert refreshed.vat_service_value == 20
    finally:
        await redis.aclose()


async def test_global_patch_invalidates_country_caches_too(
    client: AsyncClient, db_session: AsyncSession
):
    """DE has no override, so it inherits the global rate as its fallback -
    warming DE's cache, then changing the global rate, must invalidate DE's
    cached entry too, or it keeps serving the pre-change value."""
    headers = await _admin_headers(db_session)
    redis = get_redis_client()
    try:
        warm = await platform_settings_cache.get_effective_settings(
            db_session, redis, country="DE"
        )
        assert warm.vat_service_value == 20

        resp = await client.patch(SETTINGS_URL, json={"vat_value": "25.00"}, headers=headers)
        assert resp.status_code == 200, resp.text

        refreshed = await platform_settings_cache.get_effective_settings(
            db_session, redis, country="DE"
        )
        assert refreshed.vat_service_value == Decimal("25.00")
    finally:
        await redis.aclose()
