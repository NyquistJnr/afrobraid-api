import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import Currency
from app.core.database import get_db
from app.core.pagination import PaginationParams
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.bookings.enums import PaymentPurpose, PaymentStatus
from app.modules.bookings.payments import admin_service as service
from app.modules.bookings.payments.schemas import PaginatedAdminPaymentsResponse
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/admin/payments", tags=["Admin - Payments"])

_require_admin = require_roles(UserType.ADMIN)


@router.get(
    "",
    response_model=APIResponse[PaginatedAdminPaymentsResponse],
    summary="List all platform payments",
    description=(
        "Admin-wide payment ledger, newest-created first. `date_from`/`date_to` "
        "bound payment creation time; `booking_date_from`/`booking_date_to` bound "
        "the appointment start. `search` matches booking reference, Stripe ids, "
        "customer name/email, and braider business/personal name/email."
    ),
)
async def list_admin_payments(
    purpose: PaymentPurpose | None = Query(default=None),
    status_filter: PaymentStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    booking_date_from: date | None = Query(default=None),
    booking_date_to: date | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    braider_id: uuid.UUID | None = Query(default=None),
    booking_id: uuid.UUID | None = Query(default=None),
    currency: Currency | None = Query(default=None),
    is_refunded: bool | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    params: PaginationParams = Depends(),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedAdminPaymentsResponse]:
    result = await service.list_admin_payments(
        db,
        params=params,
        purpose=purpose,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        booking_date_from=booking_date_from,
        booking_date_to=booking_date_to,
        customer_id=customer_id,
        braider_id=braider_id,
        booking_id=booking_id,
        currency=currency,
        is_refunded=is_refunded,
        search=search,
    )
    return APIResponse(data=result)
