from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import Currency
from app.core.database import get_db
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.bookings import service
from app.modules.bookings.enums import BookingStatus, PaymentSchedule
from app.modules.bookings.schemas import (
    AdminBarChartResponse,
    AdminBookingStatsResponse,
    AdminPlatformFinancialsResponse,
    AdminRevenueChartResponse,
    AdminStylePieChartResponse,
)
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/admin/dashboard", tags=["Admin - Dashboard"])

_require_admin = require_roles(UserType.ADMIN)


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.get(
    "/overview",
    response_model=APIResponse[AdminBookingStatsResponse],
    summary="Get platform dashboard overview",
)
async def get_platform_overview(
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminBookingStatsResponse]:
    result = await service.get_admin_platform_overview(
        db,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        created_from=created_from,
        created_to=created_to,
        payment_date_from=payment_date_from,
        payment_date_to=payment_date_to,
        country=country,
        currency=currency,
        is_mobile=is_mobile,
        payment_schedule=payment_schedule,
        search=search,
    )
    return APIResponse(data=result)


@router.get(
    "/financials",
    response_model=APIResponse[AdminPlatformFinancialsResponse],
    summary="Get platform financial dashboard totals",
)
async def get_platform_financials(
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminPlatformFinancialsResponse]:
    result = await service.get_admin_platform_financials(
        db,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        created_from=created_from,
        created_to=created_to,
        payment_date_from=payment_date_from,
        payment_date_to=payment_date_to,
        country=country,
        currency=currency,
        is_mobile=is_mobile,
        payment_schedule=payment_schedule,
        search=search,
    )
    return APIResponse(data=result)


@router.get(
    "/charts/revenue",
    response_model=APIResponse[AdminRevenueChartResponse],
    summary="Get platform GMV line chart",
)
async def get_platform_revenue_chart(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    interval: Literal["day", "week", "month"] = Query(default="day"),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminRevenueChartResponse]:
    result = await service.get_admin_platform_revenue_chart(
        db,
        date_from=date_from,
        date_to=date_to,
        payment_date_from=payment_date_from,
        payment_date_to=payment_date_to,
        interval=interval,
        country=country,
        currency=currency,
        is_mobile=is_mobile,
        payment_schedule=payment_schedule,
        search=search,
    )
    return APIResponse(data=result)


@router.get(
    "/charts/weekday",
    response_model=APIResponse[AdminBarChartResponse],
    summary="Get platform weekday bar chart",
)
async def get_platform_weekday_chart(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminBarChartResponse]:
    result = await service.get_admin_platform_weekday_chart(
        db,
        date_from=date_from,
        date_to=date_to,
        payment_date_from=payment_date_from,
        payment_date_to=payment_date_to,
        country=country,
        currency=currency,
        is_mobile=is_mobile,
        payment_schedule=payment_schedule,
        search=search,
    )
    return APIResponse(data=result)


@router.get(
    "/charts/status",
    response_model=APIResponse[AdminBarChartResponse],
    summary="Get platform booking status bar chart",
)
async def get_platform_status_chart(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminBarChartResponse]:
    result = await service.get_admin_platform_status_chart(
        db,
        date_from=date_from,
        date_to=date_to,
        payment_date_from=payment_date_from,
        payment_date_to=payment_date_to,
        country=country,
        currency=currency,
        is_mobile=is_mobile,
        payment_schedule=payment_schedule,
        search=search,
    )
    return APIResponse(data=result)


@router.get(
    "/charts/countries",
    response_model=APIResponse[AdminBarChartResponse],
    summary="Get platform country bar chart",
)
async def get_platform_country_chart(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminBarChartResponse]:
    result = await service.get_admin_platform_country_chart(
        db,
        date_from=date_from,
        date_to=date_to,
        payment_date_from=payment_date_from,
        payment_date_to=payment_date_to,
        country=country,
        currency=currency,
        is_mobile=is_mobile,
        payment_schedule=payment_schedule,
        search=search,
    )
    return APIResponse(data=result)


@router.get(
    "/charts/styles",
    response_model=APIResponse[AdminStylePieChartResponse],
    summary="Get platform most-booked styles pie chart",
)
async def get_platform_style_chart(
    request: Request,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=8, ge=1, le=25),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminStylePieChartResponse]:
    result = await service.get_admin_platform_style_pie_chart(
        db,
        date_from=date_from,
        date_to=date_to,
        payment_date_from=payment_date_from,
        payment_date_to=payment_date_to,
        country=country,
        currency=currency,
        is_mobile=is_mobile,
        payment_schedule=payment_schedule,
        search=search,
        locale=_locale(request),
        limit=limit,
    )
    return APIResponse(data=result)
