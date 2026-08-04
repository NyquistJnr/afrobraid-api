import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.bookings import repository
from app.modules.bookings.schemas import BookingResponse
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User

router = APIRouter(prefix="/me/bookings", tags=["Braiders - Bookings"])


@router.get(
    "/",
    response_model=list[BookingResponse],
)
async def list_braider_bookings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
):
    # Only braiders have braider_id in bookings
    bookings = await repository.get_braider_bookings(
        db, current_user.id, limit=limit, offset=offset
    )
    return bookings


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
)
async def get_booking(
    booking_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.core.exceptions import BookingNotFoundError

    booking = await repository.get_booking_by_id(db, booking_id)
    if not booking or booking.braider_id != current_user.id:
        raise BookingNotFoundError()
    return booking
