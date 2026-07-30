from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.modules.auth.tasks import send_otp_email_task

settings = get_settings()


async def startup(ctx: dict) -> None:
    configure_logging()


class WorkerSettings:
    functions = [send_otp_email_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
