from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import Request

from app.core.config import get_settings

settings = get_settings()


async def create_arq_pool() -> ArqRedis:
    return await create_pool(RedisSettings.from_dsn(settings.redis_url))


def get_task_queue(request: Request) -> ArqRedis:
    return request.app.state.arq_pool
