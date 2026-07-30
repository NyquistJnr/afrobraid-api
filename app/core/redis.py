from collections.abc import AsyncGenerator

from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

settings = get_settings()

_pool = ConnectionPool.from_url(settings.redis_url, decode_responses=True)


def get_redis_client() -> Redis:
    return Redis(connection_pool=_pool)


async def get_redis() -> AsyncGenerator[Redis]:
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()
