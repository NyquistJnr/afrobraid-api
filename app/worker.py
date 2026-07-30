from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging

# Ensure every module's models are registered on Base.metadata. Tasks touch
# tables with FKs (e.g. braider_profiles -> users) that aren't otherwise
# imported by whichever task modules happen to be wired into this worker,
# and SQLAlchemy can't resolve a string ForeignKey("users.id") reference
# unless the referenced table has been registered somewhere first.
from app.modules.auth import models as auth_models  # noqa: F401,E402
from app.modules.auth.tasks import send_otp_email_task
from app.modules.braiders import models as braiders_models  # noqa: F401,E402
from app.modules.braiders.offerings import models as braider_offerings_models  # noqa: F401,E402
from app.modules.braiders.portfolio import models as braider_portfolio_models  # noqa: F401,E402
from app.modules.braiders.portfolio.tasks import translate_portfolio_caption_task
from app.modules.braiders.tasks import translate_bio_task
from app.modules.styles import models as styles_models  # noqa: F401,E402
from app.modules.styles.tasks import translate_style_text_task
from app.modules.users import models as users_models  # noqa: F401,E402

settings = get_settings()


async def startup(ctx: dict) -> None:
    configure_logging()


class WorkerSettings:
    functions = [
        send_otp_email_task,
        translate_bio_task,
        translate_style_text_task,
        translate_portfolio_caption_task,
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
