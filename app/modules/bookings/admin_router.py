import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import Currency
from app.core.database import get_db
from app.core.pagination import PaginationParams
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.bookings import service
from app.modules.bookings.enums import BookingStatus, PaymentSchedule
from app.modules.bookings.schemas import (
    AdminBarChartResponse,
    AdminBookingResponse,
    AdminBookingStatsResponse,
    AdminRevenueChartResponse,
    AdminStylePieChartResponse,
    PaginatedAdminBookingsResponse,
)
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/admin/bookings", tags=["Admin - Bookings"])

_require_admin = require_roles(UserType.ADMIN)


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.get(
    "",
    response_model=APIResponse[PaginatedAdminBookingsResponse],
    summary="List all platform bookings",
    description=(
        "Admin-wide booking search, newest-created first. `date_from`/`date_to` "
        "bound the appointment start (`starts_at`), while `created_from`/"
        "`created_to` bound when the booking was made. `search` matches booking "
        "reference, style, customer name/email, and braider business/personal name/email."
    ),
)
async def list_admin_bookings(
    request: Request,
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    braider_id: uuid.UUID | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    params: PaginationParams = Depends(),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedAdminBookingsResponse]:
    result = await service.list_admin_bookings(
        db,
        params=params,
        locale=_locale(request),
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        created_from=created_from,
        created_to=created_to,
        customer_id=customer_id,
        braider_id=braider_id,
        country=country,
        currency=currency,
        is_mobile=is_mobile,
        payment_schedule=payment_schedule,
        search=search,
    )
    return APIResponse(data=result)


@router.get(
    "/braiders/{braider_id}/stats",
    response_model=APIResponse[AdminBookingStatsResponse],
    summary="Get admin booking stats for a braider",
    description=(
        "`date_from`/`date_to` bound appointment start; `created_from`/`created_to` "
        "bound booking creation; `payment_date_from`/`payment_date_to` bound payment creation "
        "for the money totals."
    ),
)
async def get_admin_braider_booking_stats(
    braider_id: uuid.UUID,
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminBookingStatsResponse]:
    result = await service.get_admin_booking_stats(
        db,
        braider_id=braider_id,
        customer_id=customer_id,
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
    "/customers/{customer_id}/stats",
    response_model=APIResponse[AdminBookingStatsResponse],
    summary="Get admin booking stats for a customer",
)
async def get_admin_customer_booking_stats(
    customer_id: uuid.UUID,
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    braider_id: uuid.UUID | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminBookingStatsResponse]:
    result = await service.get_admin_booking_stats(
        db,
        customer_id=customer_id,
        braider_id=braider_id,
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
    "/braiders/{braider_id}/customers/{customer_id}/stats",
    response_model=APIResponse[AdminBookingStatsResponse],
    summary="Get admin booking stats for a braider/customer pair",
)
async def get_admin_braider_customer_booking_stats(
    braider_id: uuid.UUID,
    customer_id: uuid.UUID,
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
    result = await service.get_admin_booking_stats(
        db,
        braider_id=braider_id,
        customer_id=customer_id,
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
    "/braiders/{braider_id}",
    response_model=APIResponse[PaginatedAdminBookingsResponse],
    summary="List all bookings for a braider",
)
async def list_admin_bookings_for_braider(
    braider_id: uuid.UUID,
    request: Request,
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    params: PaginationParams = Depends(),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedAdminBookingsResponse]:
    result = await service.list_admin_bookings_for_braider(
        db,
        braider_id=braider_id,
        params=params,
        locale=_locale(request),
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        created_from=created_from,
        created_to=created_to,
        customer_id=customer_id,
        country=country,
        currency=currency,
        is_mobile=is_mobile,
        payment_schedule=payment_schedule,
        search=search,
    )
    return APIResponse(data=result)


@router.get(
    "/customers/{customer_id}",
    response_model=APIResponse[PaginatedAdminBookingsResponse],
    summary="List all bookings for a customer",
)
async def list_admin_bookings_for_customer(
    customer_id: uuid.UUID,
    request: Request,
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    braider_id: uuid.UUID | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    params: PaginationParams = Depends(),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedAdminBookingsResponse]:
    result = await service.list_admin_bookings_for_customer(
        db,
        customer_id=customer_id,
        params=params,
        locale=_locale(request),
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        created_from=created_from,
        created_to=created_to,
        braider_id=braider_id,
        country=country,
        currency=currency,
        is_mobile=is_mobile,
        payment_schedule=payment_schedule,
        search=search,
    )
    return APIResponse(data=result)


@router.get(
    "/braiders/{braider_id}/customers/{customer_id}",
    response_model=APIResponse[PaginatedAdminBookingsResponse],
    summary="List all bookings shared by a braider and customer",
)
async def list_admin_bookings_for_braider_customer(
    braider_id: uuid.UUID,
    customer_id: uuid.UUID,
    request: Request,
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    params: PaginationParams = Depends(),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedAdminBookingsResponse]:
    result = await service.list_admin_bookings_for_braider(
        db,
        braider_id=braider_id,
        customer_id=customer_id,
        params=params,
        locale=_locale(request),
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        created_from=created_from,
        created_to=created_to,
        country=country,
        currency=currency,
        is_mobile=is_mobile,
        payment_schedule=payment_schedule,
        search=search,
    )
    return APIResponse(data=result)


@router.get(
    "/braiders/{braider_id}/charts/revenue",
    response_model=APIResponse[AdminRevenueChartResponse],
    summary="Get a braider revenue line chart",
)
async def get_admin_braider_revenue_chart(
    braider_id: uuid.UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    interval: Literal["day", "week", "month"] = Query(default="day"),
    customer_id: uuid.UUID | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminRevenueChartResponse]:
    result = await service.get_admin_revenue_chart(
        db,
        braider_id=braider_id,
        customer_id=customer_id,
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
    "/customers/{customer_id}/charts/revenue",
    response_model=APIResponse[AdminRevenueChartResponse],
    summary="Get a customer spend line chart",
)
async def get_admin_customer_revenue_chart(
    customer_id: uuid.UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    interval: Literal["day", "week", "month"] = Query(default="day"),
    braider_id: uuid.UUID | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminRevenueChartResponse]:
    result = await service.get_admin_revenue_chart(
        db,
        customer_id=customer_id,
        braider_id=braider_id,
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
    "/braiders/{braider_id}/customers/{customer_id}/charts/revenue",
    response_model=APIResponse[AdminRevenueChartResponse],
    summary="Get a braider/customer relationship revenue line chart",
)
async def get_admin_pair_revenue_chart(
    braider_id: uuid.UUID,
    customer_id: uuid.UUID,
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
    result = await service.get_admin_revenue_chart(
        db,
        braider_id=braider_id,
        customer_id=customer_id,
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
    "/braiders/{braider_id}/charts/weekday",
    response_model=APIResponse[AdminBarChartResponse],
    summary="Get a braider weekday bar chart",
)
async def get_admin_braider_weekday_chart(
    braider_id: uuid.UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminBarChartResponse]:
    result = await service.get_admin_weekday_chart(
        db,
        braider_id=braider_id,
        customer_id=customer_id,
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
    "/customers/{customer_id}/charts/weekday",
    response_model=APIResponse[AdminBarChartResponse],
    summary="Get a customer weekday bar chart",
)
async def get_admin_customer_weekday_chart(
    customer_id: uuid.UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    braider_id: uuid.UUID | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminBarChartResponse]:
    result = await service.get_admin_weekday_chart(
        db,
        customer_id=customer_id,
        braider_id=braider_id,
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
    "/braiders/{braider_id}/customers/{customer_id}/charts/weekday",
    response_model=APIResponse[AdminBarChartResponse],
    summary="Get a braider/customer weekday bar chart",
)
async def get_admin_pair_weekday_chart(
    braider_id: uuid.UUID,
    customer_id: uuid.UUID,
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
    result = await service.get_admin_weekday_chart(
        db,
        braider_id=braider_id,
        customer_id=customer_id,
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
    "/braiders/{braider_id}/charts/status",
    response_model=APIResponse[AdminBarChartResponse],
    summary="Get a braider status bar chart",
)
async def get_admin_braider_status_chart(
    braider_id: uuid.UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminBarChartResponse]:
    result = await service.get_admin_status_chart(
        db,
        braider_id=braider_id,
        customer_id=customer_id,
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
    "/customers/{customer_id}/charts/status",
    response_model=APIResponse[AdminBarChartResponse],
    summary="Get a customer status bar chart",
)
async def get_admin_customer_status_chart(
    customer_id: uuid.UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    braider_id: uuid.UUID | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminBarChartResponse]:
    result = await service.get_admin_status_chart(
        db,
        customer_id=customer_id,
        braider_id=braider_id,
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
    "/braiders/{braider_id}/customers/{customer_id}/charts/status",
    response_model=APIResponse[AdminBarChartResponse],
    summary="Get a braider/customer status bar chart",
)
async def get_admin_pair_status_chart(
    braider_id: uuid.UUID,
    customer_id: uuid.UUID,
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
    result = await service.get_admin_status_chart(
        db,
        braider_id=braider_id,
        customer_id=customer_id,
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
    "/braiders/{braider_id}/charts/styles",
    response_model=APIResponse[AdminStylePieChartResponse],
    summary="Get a braider most-booked styles pie chart",
)
async def get_admin_braider_style_chart(
    braider_id: uuid.UUID,
    request: Request,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=8, ge=1, le=25),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminStylePieChartResponse]:
    result = await service.get_admin_style_pie_chart(
        db,
        braider_id=braider_id,
        customer_id=customer_id,
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


@router.get(
    "/customers/{customer_id}/charts/styles",
    response_model=APIResponse[AdminStylePieChartResponse],
    summary="Get a customer most-booked styles pie chart",
)
async def get_admin_customer_style_chart(
    customer_id: uuid.UUID,
    request: Request,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    braider_id: uuid.UUID | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: Currency | None = Query(default=None),
    is_mobile: bool | None = Query(default=None),
    payment_schedule: PaymentSchedule | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=8, ge=1, le=25),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminStylePieChartResponse]:
    result = await service.get_admin_style_pie_chart(
        db,
        customer_id=customer_id,
        braider_id=braider_id,
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


@router.get(
    "/braiders/{braider_id}/customers/{customer_id}/charts/styles",
    response_model=APIResponse[AdminStylePieChartResponse],
    summary="Get a braider/customer most-booked styles pie chart",
)
async def get_admin_pair_style_chart(
    braider_id: uuid.UUID,
    customer_id: uuid.UUID,
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
    result = await service.get_admin_style_pie_chart(
        db,
        braider_id=braider_id,
        customer_id=customer_id,
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


@router.get(
    "/{booking_id}",
    response_model=APIResponse[AdminBookingResponse],
    summary="Get any booking by id",
)
async def get_admin_booking(
    booking_id: uuid.UUID,
    request: Request,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminBookingResponse]:
    result = await service.get_admin_booking(db, booking_id, locale=_locale(request))
    return APIResponse(data=result)
