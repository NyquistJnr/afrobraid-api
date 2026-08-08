import logging
import uuid

from app.core.database import AsyncSessionLocal
from app.modules.braiders.models import BioSource
from app.modules.reviews import repository as reviews_repo
from app.shared.translation.client import TranslationError, translate_text

logger = logging.getLogger("app.tasks.reviews")

TASK_TRANSLATE_REVIEW_COMMENT = "translate_review_comment_task"


async def translate_review_comment_task(
    ctx: dict,
    *,
    review_id: str,
    source_locale: str,
    source_text: str,
    target_locales: list[str],
) -> None:
    async with AsyncSessionLocal() as db:
        review = await reviews_repo.get_by_id(db, uuid.UUID(review_id))
        if review is None:
            return

        for target_locale in target_locales:
            source_field = f"comment_{target_locale}_source"
            if getattr(review, source_field) != BioSource.PENDING:
                # Customer hand-edited this locale (or re-triggered translation)
                # before we got to it - don't clobber whatever it is now.
                continue

            try:
                translated = await translate_text(
                    source_text, source_lang=source_locale, target_lang=target_locale
                )
            except TranslationError:
                logger.exception(
                    "Review comment translation failed for review %s (%s -> %s)",
                    review_id,
                    source_locale,
                    target_locale,
                )
                setattr(review, source_field, BioSource.FAILED)
                await db.commit()
                continue

            setattr(review, f"comment_{target_locale}", translated)
            setattr(review, source_field, BioSource.MACHINE)
            await db.commit()
