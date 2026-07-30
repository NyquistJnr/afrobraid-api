import logging
import uuid

from app.core.database import AsyncSessionLocal
from app.modules.styles.models import AddOn, Style, StyleCategory, StyleVariation, TranslationSource
from app.shared.translation.client import TranslationError, translate_text

logger = logging.getLogger("app.tasks.styles")

TASK_TRANSLATE_STYLE_TEXT = "translate_style_text_task"

_MODEL_BY_ENTITY_TYPE = {
    "style_category": StyleCategory,
    "style": Style,
    "style_variation": StyleVariation,
    "addon": AddOn,
}


async def translate_style_text_task(
    ctx: dict,
    *,
    entity_type: str,
    entity_id: str,
    field: str,
    source_locale: str,
    source_text: str,
    target_locales: list[str],
) -> None:
    """Translates a single `{field}_{locale}` text field (e.g. "name" on a Style,
    Category, Variation, or AddOn) into each target locale - the same fan-out
    `braiders.tasks.translate_bio_task` does for a braider's bio, generalized
    across the several catalog models that carry translatable text."""
    model = _MODEL_BY_ENTITY_TYPE[entity_type]

    async with AsyncSessionLocal() as db:
        entity = await db.get(model, uuid.UUID(entity_id))
        if entity is None:
            return

        for target_locale in target_locales:
            source_field = f"{field}_{target_locale}_source"
            if getattr(entity, source_field) != TranslationSource.PENDING:
                # Hand-edited (or re-triggered) before we got to it - don't clobber it.
                continue

            try:
                translated = await translate_text(
                    source_text, source_lang=source_locale, target_lang=target_locale
                )
            except TranslationError:
                logger.exception(
                    "Style catalog translation failed for %s %s.%s (%s -> %s)",
                    entity_type,
                    entity_id,
                    field,
                    source_locale,
                    target_locale,
                )
                setattr(entity, source_field, TranslationSource.FAILED)
                await db.commit()
                continue

            setattr(entity, f"{field}_{target_locale}", translated)
            setattr(entity, source_field, TranslationSource.MACHINE)
            await db.commit()
