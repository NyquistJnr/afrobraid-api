import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.queue import get_task_queue
from app.core.response import APIResponse
from app.modules.auth.dependencies import get_current_user
from app.modules.tryon import service
from app.modules.tryon.schemas import (
    TryOnCreateRequest,
    TryOnResponse,
    TryOnUploadUrlRequest,
    TryOnUploadUrlResponse,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/tryon", tags=["Hairstyle Try-On"])


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.post(
    "/upload-url",
    response_model=APIResponse[TryOnUploadUrlResponse],
    summary="Step 1: get a photo upload URL",
    description=(
        "Returns a presigned URL to PUT the client's photo directly to storage. "
        "After uploading, call `POST /api/v1/tryon` with the returned `object_key` "
        "plus a style and/or a description of the desired hairstyle."
    ),
)
async def request_upload_url(
    payload: TryOnUploadUrlRequest,
    user: User = Depends(get_current_user),
) -> APIResponse[TryOnUploadUrlResponse]:
    result = await service.request_upload_url(user.id, data=payload)
    return APIResponse(data=result)


@router.post(
    "",
    response_model=APIResponse[TryOnResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Step 2: start generating the try-on",
    description=(
        "Call this after successfully PUTing the photo to the `upload_url` from "
        "the previous step. Generation happens in the background - the response "
        "comes back with `status: PROCESSING`; poll `GET /api/v1/tryon/{id}` (or "
        "`GET /api/v1/tryon` for your history) until `status` is `COMPLETED` (see "
        "`result_url`) or `FAILED`. Your original photo is deleted from storage as "
        "soon as processing finishes."
    ),
)
async def create_tryon(
    payload: TryOnCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[TryOnResponse]:
    result = await service.create_tryon(db, user.id, data=payload, locale=_locale(request), queue=queue)
    return APIResponse(data=result)


@router.get(
    "",
    response_model=APIResponse[list[TryOnResponse]],
    summary="Your try-on history",
)
async def list_tryons(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[TryOnResponse]]:
    result = await service.list_tryons(db, user.id, locale=_locale(request))
    return APIResponse(data=result)


@router.get(
    "/{tryon_id}",
    response_model=APIResponse[TryOnResponse],
    summary="Check on (or fetch the result of) a try-on",
)
async def get_tryon(
    tryon_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[TryOnResponse]:
    result = await service.get_tryon(db, user.id, tryon_id, locale=_locale(request))
    return APIResponse(data=result)


@router.delete(
    "/{tryon_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a try-on and its photos",
)
async def delete_tryon(
    tryon_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_tryon(db, user.id, tryon_id)
