import pytest

from app.core.cache import delete, get_json, set_json
from app.core.redis import get_redis_client

pytestmark = pytest.mark.asyncio


async def test_set_and_get_json_round_trips():
    redis = get_redis_client()
    try:
        await set_json(redis, "test:key", {"a": 1, "b": "two"}, ttl_seconds=60)
        value = await get_json(redis, "test:key")
        assert value == {"a": 1, "b": "two"}
    finally:
        await redis.aclose()


async def test_get_json_returns_none_on_miss():
    redis = get_redis_client()
    try:
        value = await get_json(redis, "test:does-not-exist")
        assert value is None
    finally:
        await redis.aclose()


async def test_set_json_applies_ttl():
    redis = get_redis_client()
    try:
        await set_json(redis, "test:ttl-key", {"x": 1}, ttl_seconds=60)
        ttl = await redis.ttl("test:ttl-key")
        assert 0 < ttl <= 60
    finally:
        await redis.aclose()


async def test_delete_removes_key():
    redis = get_redis_client()
    try:
        await set_json(redis, "test:to-delete", {"x": 1}, ttl_seconds=60)
        await delete(redis, "test:to-delete")
        assert await get_json(redis, "test:to-delete") is None
    finally:
        await redis.aclose()


async def test_delete_with_no_keys_is_a_no_op():
    redis = get_redis_client()
    try:
        await delete(redis)  # must not raise
    finally:
        await redis.aclose()
