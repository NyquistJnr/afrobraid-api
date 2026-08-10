from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginationParams
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.bookings.enums import PaymentPurpose, PaymentStatus
from app.modules.bookings.payments import braider_service as service
from app.modules.bookings.payments.schemas import PaginatedPaymentsResponse, PaymentStatsResponse
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/braiders/me/payments", tags=["Braider - Payments"])

_require_braider = require_roles(UserType.BRAIDER)


@router.get(
    "/stats",
    response_model=APIResponse[PaymentStatsResponse],
    summary="Get your payment stats",
    description=(
        "Money-flow summary: total received, total refunded, net revenue, "
        "and pending. Filter by `status` and bound by `date_from`/`date_to` "
        "(when the payment was created, not the booking's appointment date)."
    ),
)
async def get_payment_stats(
    status_filter: PaymentStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaymentStatsResponse]:
    result = await service.get_payment_stats(
        db, user_id=user.id, status=status_filter, date_from=date_from, date_to=date_to
    )
    return APIResponse(data=result)


@router.get(
    "",
    response_model=APIResponse[PaginatedPaymentsResponse],
    summary="List your payments",
    description=(
        "Every payment (deposit, full, or balance) across your bookings, "
        "most recent first. `is_refunded` reflects amount_refunded > 0. "
        "Filter by `purpose`, `status`, and `date_from`/`date_to`."
    ),
)
async def list_payments(
    purpose: PaymentPurpose | None = Query(default=None),
    status_filter: PaymentStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    params: PaginationParams = Depends(),
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedPaymentsResponse]:
    result = await service.list_payments(
        db,
        user_id=user.id,
        params=params,
        purpose=purpose,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
    )
    return APIResponse(data=result)
