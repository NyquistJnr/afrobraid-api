"""Generic JSON cache helpers over the shared Redis client (`app.core.redis`).

This is the first cache module in the repo - the only prior Redis consumer
is `app.core.rate_limit`. `get_redis()`'s pool is created with
`decode_responses=True`, so values round-trip as `str`, never `bytes`;
callers are responsible for JSON-serializable payloads (e.g. Decimals as
strings) since `json` doesn't know about them natively.

Module-specific cache modules (e.g. `platform_settings/cache.py`) own their
own key naming and TTLs and call through these primitives rather than
touching `redis` directly, so invalidation points stay easy to grep for.
"""

import json
from typing import Any

from redis.asyncio import Redis


async def get_json(redis: Redis, key: str) -> Any | None:
    raw = await redis.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def set_json(redis: Redis, key: str, value: Any, *, ttl_seconds: int) -> None:
    await redis.set(key, json.dumps(value), ex=ttl_seconds)


async def delete(redis: Redis, *keys: str) -> None:
    if keys:
        await redis.delete(*keys)
