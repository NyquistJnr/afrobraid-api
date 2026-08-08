import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginatedData, PaginationParams
from app.core.queue import get_task_queue
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.reviews import service
from app.modules.reviews.schemas import PublicReviewResponse, ReviewResponse, ReviewUpsertRequest
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/braiders/{braider_id}/reviews", tags=["Reviews"])

_require_customer = require_roles(UserType.CUSTOMER)


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.get(
    "",
    response_model=APIResponse[PaginatedData[PublicReviewResponse]],
    summary="List a braider's public reviews",
    description=(
        "Public, no auth required. Only returns reviews whose written comment "
        "has been approved by an admin (or that have no comment at all) - "
        "ratings without an approved comment aren't listed here, but they're "
        "already counted in the braider's `rating` shown on search/detail."
    ),
)
async def list_reviews(
    braider_id: uuid.UUID,
    request: Request,
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedData[PublicReviewResponse]]:
    result = await service.list_public_reviews(db, braider_id, params=params, locale=_locale(request))
    return APIResponse(data=result)


@router.get(
    "/me",
    response_model=APIResponse[ReviewResponse],
    summary="Get your review for this braider",
)
async def get_my_review(
    braider_id: uuid.UUID,
    user: User = Depends(_require_customer),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ReviewResponse]:
    result = await service.get_my_review(db, user_id=user.id, braider_id=braider_id)
    return APIResponse(data=result)


@router.put(
    "/me",
    response_model=APIResponse[ReviewResponse],
    summary="Rate and review this braider",
    description=(
        "Creates your review the first time, updates it on every call after - "
        "you can only ever have one review per braider. Requires at least one "
        "booking with this braider that reached a successful payment. The "
        "`rating` takes effect immediately; if you send a `comment`, it's "
        "saved in your current locale and auto-translated into the others, "
        "and needs admin approval before it's publicly visible (editing an "
        "already-approved comment resets it to pending re-approval)."
    ),
)
async def upsert_review(
    braider_id: uuid.UUID,
    payload: ReviewUpsertRequest,
    request: Request,
    user: User = Depends(_require_customer),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[ReviewResponse]:
    result = await service.upsert_review(
        db, user_id=user.id, braider_id=braider_id, data=payload, locale=_locale(request), queue=queue
    )
    return APIResponse(data=result)
