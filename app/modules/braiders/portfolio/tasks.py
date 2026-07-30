import logging
import uuid

from app.core.database import AsyncSessionLocal
from app.modules.braiders.models import BioSource
from app.modules.braiders.portfolio import repository as portfolio_repo
from app.shared.translation.client import TranslationError, translate_text

logger = logging.getLogger("app.tasks.portfolio")

TASK_TRANSLATE_PORTFOLIO_CAPTION = "translate_portfolio_caption_task"


async def translate_portfolio_caption_task(
    ctx: dict,
    *,
    image_id: str,
    source_locale: str,
    source_text: str,
    target_locales: list[str],
) -> None:
    async with AsyncSessionLocal() as db:
        image = await portfolio_repo.get_image_by_id(db, uuid.UUID(image_id))
        if image is None:
            return

        for target_locale in target_locales:
            source_field = f"caption_{target_locale}_source"
            if getattr(image, source_field) != BioSource.PENDING:
                # Braider hand-edited this locale (or re-triggered translation)
                # before we got to it - don't clobber whatever it is now.
                continue

            try:
                translated = await translate_text(
                    source_text, source_lang=source_locale, target_lang=target_locale
                )
            except TranslationError:
                logger.exception(
                    "Portfolio caption translation failed for image %s (%s -> %s)",
                    image_id,
                    source_locale,
                    target_locale,
                )
                setattr(image, source_field, BioSource.FAILED)
                await db.commit()
                continue

            setattr(image, f"caption_{target_locale}", translated)
            setattr(image, source_field, BioSource.MACHINE)
            await db.commit()
