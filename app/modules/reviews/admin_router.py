import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginatedData, PaginationParams
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.reviews import service
from app.modules.reviews.models import ReviewStatus
from app.modules.reviews.schemas import AdminReviewResponse
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/admin/reviews", tags=["Admin - Reviews"])

_require_admin = require_roles(UserType.ADMIN)


@router.get(
    "",
    response_model=APIResponse[PaginatedData[AdminReviewResponse]],
    summary="List reviews for moderation",
    description="Defaults to `status=PENDING` (the moderation queue) - pass another `status` or omit the filter to browse all reviews.",
)
async def list_reviews(
    status_filter: ReviewStatus | None = Query(default=ReviewStatus.PENDING, alias="status"),
    params: PaginationParams = Depends(),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedData[AdminReviewResponse]]:
    result = await service.list_admin_reviews(db, params=params, status=status_filter)
    return APIResponse(data=result)


@router.post(
    "/{review_id}/approve",
    response_model=APIResponse[AdminReviewResponse],
    summary="Approve a review's written comment",
)
async def approve_review(
    review_id: uuid.UUID,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminReviewResponse]:
    result = await service.approve_review(db, review_id)
    return APIResponse(data=result)


@router.post(
    "/{review_id}/reject",
    response_model=APIResponse[AdminReviewResponse],
    summary="Reject a review",
    description="Also excludes this review's rating from the braider's average until it's approved again.",
)
async def reject_review(
    review_id: uuid.UUID,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminReviewResponse]:
    result = await service.reject_review(db, review_id)
    return APIResponse(data=result)
