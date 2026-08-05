import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginationParams
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.bookings import service
from app.modules.bookings.schemas import BookingResponse, PaginatedBookingsResponse
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/braiders/me/bookings", tags=["Braider - Bookings"])

_require_braider = require_roles(UserType.BRAIDER)


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.get("", response_model=APIResponse[PaginatedBookingsResponse], summary="List your bookings")
async def list_braider_bookings(
    request: Request,
    params: PaginationParams = Depends(),
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedBookingsResponse]:
    result = await service.list_braider_bookings(db, user_id=user.id, params=params, locale=_locale(request))
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
