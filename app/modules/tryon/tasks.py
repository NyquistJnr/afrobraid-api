import logging
import uuid

from app.core import storage
from app.core.database import AsyncSessionLocal
from app.modules.tryon import repository as tryon_repo
from app.modules.tryon.client import HuggingFaceApiError, generate_hairstyle_image
from app.modules.tryon.models import TryOnStatus

logger = logging.getLogger("app.tasks.tryon")

TASK_GENERATE_HAIRSTYLE_TRYON = "generate_hairstyle_tryon_task"

_RESULT_CONTENT_TYPE = "image/jpeg"


async def generate_hairstyle_tryon_task(ctx: dict, *, tryon_id: str) -> None:
    async with AsyncSessionLocal() as db:
        tryon = await tryon_repo.get_tryon_by_id(db, uuid.UUID(tryon_id))
        if tryon is None or tryon.status != TryOnStatus.PROCESSING:
            # Deleted (or otherwise moved on) before we got to it.
            return

        source_key = tryon.source_object_key
        original_bytes = storage.get_object(source_key) if source_key else None
        if original_bytes is None or source_key is None:
            logger.error("Try-on %s: source photo %r is missing", tryon_id, source_key)
            tryon.status = TryOnStatus.FAILED
            tryon.source_object_key = None
            await db.commit()
            return

        try:
            result_bytes = await generate_hairstyle_image(original_bytes, instruction=tryon.prompt)
        except HuggingFaceApiError:
            logger.exception("Try-on %s: Hugging Face generation failed", tryon_id)
            tryon.status = TryOnStatus.FAILED
            await db.commit()
            # The original photo is kept on a failed run so a future retry
            # feature (or manual support follow-up) doesn't need a re-upload -
            # it's deleted below only once a result actually exists.
            return

        result_key = f"tryon/{tryon.user_id}/result/{uuid.uuid4()}.jpg"
        storage.put_object(result_key, result_bytes, content_type=_RESULT_CONTENT_TYPE)
        storage.delete_object(source_key)

        tryon.result_object_key = result_key
        tryon.source_object_key = None
        tryon.status = TryOnStatus.COMPLETED
        await db.commit()
