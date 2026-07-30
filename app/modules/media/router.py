from fastapi import APIRouter, Depends, Request

from app.modules.auth.dependencies import get_current_user
from app.modules.media import service
from app.modules.media.schemas import DeleteMediaRequest, DeleteMediaResponse
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/media", tags=["Media"])


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.delete("", response_model=DeleteMediaResponse)
async def delete_media(
    payload: DeleteMediaRequest,
    request: Request,
    user: User = Depends(get_current_user),
) -> DeleteMediaResponse:
    return await service.delete_media(user, data=payload, locale=_locale(request))
