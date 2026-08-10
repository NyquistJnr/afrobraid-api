from arq import cron
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
from app.modules.bookings import models as bookings_models  # noqa: F401,E402
from app.modules.bookings.calculations import (
    models as booking_calculations_models,  # noqa: F401,E402
)
from app.modules.bookings.calculations.cron import expire_booking_calculations_cron
from app.modules.bookings.cron import expire_booking_holds_cron
from app.modules.bookings.payments import models as booking_payments_models  # noqa: F401,E402
from app.modules.bookings.tasks import (
    send_booking_confirmed_email_task,
    send_payment_notification_task,
    send_payment_receipt_email_task,
)
from app.modules.braiders import models as braiders_models  # noqa: F401,E402
from app.modules.braiders.offerings import models as braider_offerings_models  # noqa: F401,E402
from app.modules.braiders.portfolio import models as braider_portfolio_models  # noqa: F401,E402
from app.modules.braiders.portfolio.tasks import translate_portfolio_caption_task
from app.modules.braiders.tasks import translate_bio_task
from app.modules.chat import models as chat_models  # noqa: F401,E402
from app.modules.chat.tasks import translate_chat_message_task
from app.modules.notifications import models as notifications_models  # noqa: F401,E402
from app.modules.reviews import models as reviews_models  # noqa: F401,E402
from app.modules.reviews.tasks import translate_review_comment_task
from app.modules.styles import models as styles_models  # noqa: F401,E402
from app.modules.styles.tasks import translate_style_text_task
from app.modules.tryon import models as tryon_models  # noqa: F401,E402
from app.modules.tryon.tasks import generate_hairstyle_tryon_task
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
        send_booking_confirmed_email_task,
        send_payment_receipt_email_task,
        send_payment_notification_task,
        translate_review_comment_task,
        generate_hairstyle_tryon_task,
        translate_chat_message_task,
    ]
    cron_jobs = [
        # Hourly, well ahead of the 2h calculation TTL - see
        # app.modules.bookings.calculations.cron.
        cron(expire_booking_calculations_cron, minute=0),
        cron(expire_booking_holds_cron, second=0),
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
