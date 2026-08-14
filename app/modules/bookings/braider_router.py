import uuid
from datetime import date

from arq import ArqRedis
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginationParams
from app.core.queue import get_task_queue
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.bookings import service
from app.modules.bookings.enums import BookingStatus
from app.modules.bookings.schemas import (
    BookingResponse,
    BraiderBookingCancelRequest,
    PaginatedBookingsResponse,
)
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/braiders/me/bookings", tags=["Braider - Bookings"])

_require_braider = require_roles(UserType.BRAIDER)


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.get(
    "",
    response_model=APIResponse[PaginatedBookingsResponse],
    summary="List your bookings",
    description=(
        "Filter by `status`, by appointment date with `date_from`/`date_to` "
        "(bounds `starts_at`, not when the booking was made; either side "
        "can be given alone), and free-text `search` (matches the style "
        "name or the customer's name)."
    ),
)
async def list_braider_bookings(
    request: Request,
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None),
    params: PaginationParams = Depends(),
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedBookingsResponse]:
    result = await service.list_braider_bookings(
        db,
        user_id=user.id,
        params=params,
        locale=_locale(request),
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    return APIResponse(data=result)


@router.get("/{booking_id}", response_model=APIResponse[BookingResponse], summary="Get a booking")
async def get_braider_booking(
    booking_id: uuid.UUID,
    request: Request,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BookingResponse]:
    result = await service.get_braider_booking(db, booking_id, user_id=user.id, locale=_locale(request))
    return APIResponse(data=result)


@router.post(
    "/{booking_id}/cancel",
    response_model=APIResponse[BookingResponse],
    summary="Cancel a confirmed booking",
    description=(
        "Braider-only, reason required. No cutoff - can cancel at any "
        "time up to the appointment. Fully refunds every succeeded "
        "payment on the booking, deposit included; the platform absorbs "
        "Stripe's non-returned processing fee. Only CONFIRMED bookings "
        "are eligible."
    ),
)
async def cancel_braider_booking(
    booking_id: uuid.UUID,
    payload: BraiderBookingCancelRequest,
    request: Request,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[BookingResponse]:
    result = await service.cancel_booking_by_braider(
        db, queue, booking_id, user_id=user.id, reason=payload.reason, locale=_locale(request)
    )
    return APIResponse(data=result)


@router.post(
    "/{booking_id}/no-show",
    response_model=APIResponse[BookingResponse],
    summary="Report the customer as a no-show",
    description=(
        "Braider-only. Only available once the appointment time has "
        "passed on a CONFIRMED or IN_PROGRESS booking. No refund - the "
        "braider is still paid in full at the normal payout delay, same "
        "as a COMPLETED booking."
    ),
)
async def mark_booking_no_show(
    booking_id: uuid.UUID,
    request: Request,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BookingResponse]:
    result = await service.mark_booking_no_show(db, booking_id, user_id=user.id, locale=_locale(request))
    return APIResponse(data=result)
