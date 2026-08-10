from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.bookings.dashboard import service
from app.modules.bookings.dashboard.schemas import (
    BookingsByWeekdayResponse,
    DashboardOverviewResponse,
    RevenueTimeSeriesResponse,
    StyleBreakdownResponse,
)
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/braiders/me/dashboard", tags=["Braider - Dashboard"])

_require_braider = require_roles(UserType.BRAIDER)


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.get(
    "/overview",
    response_model=APIResponse[DashboardOverviewResponse],
    summary="Get your dashboard overview stats",
    description=(
        "Headline metrics for the dashboard's stat tiles: booking counts by "
        "outcome, completion/cancellation rates, revenue (your share, not "
        "gross), average booking value, unique/repeat customers, and your "
        "cached rating. Bounds `starts_at` with `date_from`/`date_to`, "
        "either side optional."
    ),
)
async def get_overview(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[DashboardOverviewResponse]:
    result = await service.get_overview(db, user_id=user.id, date_from=date_from, date_to=date_to)
    return APIResponse(data=result)


@router.get(
    "/revenue-timeseries",
    response_model=APIResponse[RevenueTimeSeriesResponse],
    summary="Get your revenue over time (line chart)",
    description=(
        "Revenue (your share) and booking count per interval bucket over "
        "`starts_at`. Defaults to the last 90 days if no date range is "
        "given, same convention as the booking timeseries endpoint."
    ),
)
async def get_revenue_timeseries(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    interval: Literal["day", "week", "month"] = Query(default="day"),
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[RevenueTimeSeriesResponse]:
    result = await service.get_revenue_timeseries(
        db, user_id=user.id, date_from=date_from, date_to=date_to, interval=interval
    )
    return APIResponse(data=result)


@router.get(
    "/bookings-by-weekday",
    response_model=APIResponse[BookingsByWeekdayResponse],
    summary="Get your busiest days of the week (bar chart)",
    description=(
        "Booking count and revenue (your share) grouped by ISO weekday of "
        "`starts_at` (1=Monday..7=Sunday). Always returns all 7 weekdays, "
        "zero-filled, for a stable bar-chart x-axis. Only counts bookings "
        "that actually occupied the calendar - cancelled/expired holds are "
        "excluded."
    ),
)
async def get_bookings_by_weekday(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BookingsByWeekdayResponse]:
    result = await service.get_bookings_by_weekday(db, user_id=user.id, date_from=date_from, date_to=date_to)
    return APIResponse(data=result)


@router.get(
    "/style-breakdown",
    response_model=APIResponse[StyleBreakdownResponse],
    summary="Get your revenue breakdown by style (pie chart)",
    description=(
        "Booking count and revenue (your share) grouped by style, ordered "
        "by revenue descending. Returns your top 8 styles individually and "
        "folds the rest into a single 'Other' slice, so the pie chart "
        "always has a manageable number of slices."
    ),
)
async def get_style_breakdown(
    request: Request,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[StyleBreakdownResponse]:
    result = await service.get_style_breakdown(
        db, user_id=user.id, date_from=date_from, date_to=date_to, locale=_locale(request)
    )
    return APIResponse(data=result)
