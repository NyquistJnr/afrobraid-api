import logging
import uuid

from app.core import ws
from app.core.database import AsyncSessionLocal
from app.modules.chat import repository as chat_repo
from app.modules.chat.models import ChatTranslationStatus
from app.shared.translation.client import TranslationError, translate_text

logger = logging.getLogger("app.tasks.chat")

TASK_TRANSLATE_CHAT_MESSAGE = "translate_chat_message_task"


async def translate_chat_message_task(
    ctx: dict,
    *,
    message_id: str,
    thread_id: str,
    source_locale: str,
    target_locale: str,
    customer_id: str,
    braider_user_id: str,
) -> None:
    async with AsyncSessionLocal() as db:
        message = await chat_repo.get_message_by_id(db, uuid.UUID(message_id))
        if message is None or message.translation_status != ChatTranslationStatus.PENDING:
            # Deleted, or already resolved (e.g. a retry racing the original) -
            # nothing left to do.
            return

        try:
            translated = await translate_text(
                message.body or "", source_lang=source_locale, target_lang=target_locale
            )
        except TranslationError:
            logger.exception(
                "Chat message translation failed for message %s (%s -> %s)",
                message_id,
                source_locale,
                target_locale,
            )
            message.translation_status = ChatTranslationStatus.FAILED
            await db.commit()
            return

        message.translated_body = translated
        message.translated_locale = target_locale
        message.translation_status = ChatTranslationStatus.DONE
        await db.commit()

    event = {
        "type": "chat_message_translated",
        "thread_id": thread_id,
        "message_id": message_id,
        "translated_body": translated,
        "translated_locale": target_locale,
    }
    await ws.publish_event(uuid.UUID(customer_id), event)
    await ws.publish_event(uuid.UUID(braider_user_id), event)
