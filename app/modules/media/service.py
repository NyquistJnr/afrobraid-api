from app.core import storage
from app.core.exceptions import ForbiddenRoleError
from app.core.i18n import t
from app.modules.media.schemas import DeleteMediaRequest, DeleteMediaResponse
from app.modules.users.models import User, UserType


def _can_delete(user: User, object_key: str) -> bool:
    if user.user_type == UserType.ADMIN:
        return True
    # Every per-user upload (logo today, portfolio/documents/etc. later) is
    # expected to live under this owner-scoped prefix, so this check
    # generalizes to future upload types without needing changes here.
    return object_key.startswith(f"braiders/{user.id}/")


async def delete_media(
    user: User, *, data: DeleteMediaRequest, locale: str
) -> DeleteMediaResponse:
    if not _can_delete(user, data.object_key):
        raise ForbiddenRoleError()

    storage.delete_object(data.object_key)
    return DeleteMediaResponse(message=t("media.deleted", locale))
