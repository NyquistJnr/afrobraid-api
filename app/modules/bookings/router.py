import uuid
from datetime import date

from arq import ArqRedis
from fastapi import APIRouter, Depends, Query, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginationParams
from app.core.queue import get_task_queue
from app.core.redis import get_redis
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.bookings import service
from app.modules.bookings.enums import BookingStatus
from app.modules.bookings.schemas import (
    BookingCreateRequest,
    BookingResponse,
    PaginatedBookingsResponse,
)
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/bookings", tags=["Bookings"])

_require_customer = require_roles(UserType.CUSTOMER)


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.post(
    "",
    response_model=APIResponse[BookingResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a booking from a price quote",
    description=(
        "Consumes a DRAFT booking calculation and an appointment time. "
        "Everything else (braider, style, add-ons, mobile address) comes "
        "from the calculation, not this request. Re-validates and re-prices "
        "against current state - if the total drifted from the quote you "
        "saw, this 409s and you should fetch a fresh calculation."
    ),
)
async def create_booking(
    payload: BookingCreateRequest,
    request: Request,
    user: User = Depends(_require_customer),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[BookingResponse]:
    result = await service.create_booking(db, redis, queue, user=user, data=payload, locale=_locale(request))
    return APIResponse(data=result)


@router.get(
    "",
    response_model=APIResponse[PaginatedBookingsResponse],
    summary="List your bookings",
    description=(
        "Filter by `status`, by appointment date with `date_from`/`date_to` "
        "(bounds `starts_at`, not when the booking was made; either side "
        "can be given alone), and free-text `search` (matches the style "
        "name or the braider's business/personal name)."
    ),
)
async def list_bookings(
    request: Request,
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None),
    params: PaginationParams = Depends(),
    user: User = Depends(_require_customer),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedBookingsResponse]:
    result = await service.list_bookings(
        db,
        user=user,
        params=params,
        locale=_locale(request),
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    return APIResponse(data=result)


@router.get(
    "/today-count",
    response_model=APIResponse[int],
    summary="Total bookings made today",
    description="Public, no auth required. No params. Counts every booking created "
    "today (UTC calendar day), regardless of status.",
)
async def get_bookings_today_count(db: AsyncSession = Depends(get_db)) -> APIResponse[int]:
    result = await service.count_bookings_today(db)
    return APIResponse(data=result)


@router.get("/{booking_id}", response_model=APIResponse[BookingResponse], summary="Get a booking")
async def get_booking(
    booking_id: uuid.UUID,
    request: Request,
    user: User = Depends(_require_customer),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BookingResponse]:
    result = await service.get_booking(db, booking_id, user=user, locale=_locale(request))
    return APIResponse(data=result)
