import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import Currency
from app.core.database import get_db
from app.core.pagination import PaginationParams
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.bookings import service
from app.modules.bookings.enums import BookingStatus, PaymentSchedule
from app.modules.bookings.schemas import AdminBookingResponse, PaginatedAdminBookingsResponse
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
