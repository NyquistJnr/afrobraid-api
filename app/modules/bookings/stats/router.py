from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.bookings.enums import BookingStatus
from app.modules.bookings.stats import service
from app.modules.bookings.stats.schemas import BookingStatsResponse, BookingTimeSeriesResponse
from app.modules.users.models import User, UserType

# NOTE: registered in app.main *before* bookings.braider_router - both
# mount at /api/v1/braiders/me/bookings, and that router's GET
# "/{booking_id}" (a uuid.UUID path param) would otherwise 422 on literal
# "stats"/"timeseries" before Starlette gets a chance to try this router's
# more specific routes.
router = APIRouter(prefix="/api/v1/braiders/me/bookings", tags=["Braider - Booking Stats"])

_require_braider = require_roles(UserType.BRAIDER)


@router.get(
    "/stats",
    response_model=APIResponse[BookingStatsResponse],
    summary="Get your booking stats",
    description=(
        "Total, completed, declined, and upcoming booking counts. Bounds "
        "`starts_at` with `date_from`/`date_to`, either side optional."
    ),
)
async def get_booking_stats(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BookingStatsResponse]:
    result = await service.get_booking_stats(db, user_id=user.id, date_from=date_from, date_to=date_to)
    return APIResponse(data=result)


@router.get(
    "/timeseries",
    response_model=APIResponse[BookingTimeSeriesResponse],
    summary="Get your booking trend, one line per status",
    description=(
        "Multi-line graph data: one count per (interval bucket, status), "
        "bucketed by `interval` over `starts_at`. Defaults to the last 90 "
        "days if no date range is given. Filter which lines come back with "
        "repeated `status` params; omit for every status that has at least "
        "one booking in range."
    ),
)
async def get_booking_timeseries(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    interval: Literal["day", "week", "month"] = Query(default="day"),
    status_filter: list[BookingStatus] | None = Query(default=None, alias="status"),
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BookingTimeSeriesResponse]:
    result = await service.get_booking_timeseries(
        db,
        user_id=user.id,
        date_from=date_from,
        date_to=date_to,
        interval=interval,
        statuses=status_filter,
    )
    return APIResponse(data=result)
