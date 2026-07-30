from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core.exceptions import RateLimitedError
from app.core.redis import get_redis


async def check_rate_limit(redis: Redis, *, key: str, limit: int, window_seconds: int) -> None:
    """Fixed-window counter. Raises RateLimitedError once `limit` hits occur within the window."""
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    if count > limit:
        ttl = await redis.ttl(key)
        raise RateLimitedError(retry_after_seconds=max(ttl, 1))


def ip_rate_limiter(*, key_prefix: str, limit: int, window_seconds: int):
    """FastAPI dependency: throttles a route per client IP."""

    async def dependency(request: Request, redis: Redis = Depends(get_redis)) -> None:
        client_ip = request.client.host if request.client else "unknown"
        await check_rate_limit(
            redis,
            key=f"ratelimit:{key_prefix}:{client_ip}",
            limit=limit,
            window_seconds=window_seconds,
        )

    return dependency
