import logging
import uuid

from app.core.database import AsyncSessionLocal
from app.modules.braiders import repository as braiders_repo
from app.modules.braiders.completion import recompute_business_info_completion
from app.modules.braiders.models import BioSource
from app.shared.translation.client import TranslationError, translate_text

logger = logging.getLogger("app.tasks.braiders")

TASK_TRANSLATE_BIO = "translate_bio_task"


async def translate_bio_task(
    ctx: dict,
    *,
    user_id: str,
    source_locale: str,
    source_text: str,
    target_locales: list[str],
) -> None:
    async with AsyncSessionLocal() as db:
        profile = await braiders_repo.get_profile_by_user_id(db, uuid.UUID(user_id))
        if profile is None:
            return

        for target_locale in target_locales:
            source_field = f"bio_{target_locale}_source"
            if getattr(profile, source_field) != BioSource.PENDING:
                # Braider hand-edited this locale (or re-triggered translation)
                # before we got to it - don't clobber whatever it is now.
                continue

            try:
                translated = await translate_text(
                    source_text, source_lang=source_locale, target_lang=target_locale
                )
            except TranslationError:
                logger.exception(
                    "Bio translation failed for user %s (%s -> %s)",
                    user_id,
                    source_locale,
                    target_locale,
                )
                setattr(profile, source_field, BioSource.FAILED)
                await db.commit()
                continue

            setattr(profile, f"bio_{target_locale}", translated)
            setattr(profile, source_field, BioSource.MACHINE)
            await db.commit()

        status = await braiders_repo.get_onboarding_status_by_user_id(db, uuid.UUID(user_id))
        if status is not None:
            recompute_business_info_completion(profile, status)
            await db.commit()
