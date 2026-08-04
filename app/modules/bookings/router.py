import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.bookings import repository, service
from app.modules.bookings.schemas import (
    BookingCreateRequest,
    BookingIntentResponse,
    BookingResponse,
)
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=BookingIntentResponse,
)
async def create_booking(
    request: BookingCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    booking, client_secret = await service.create_booking(
        db=db,
        customer=current_user,
        calculation_id=request.calculation_id,
        starts_at=request.starts_at,
    )
    # The session isn't committed by the service to allow atomic failure.
    # We commit here after Stripe responds.
    await db.commit()
    await db.refresh(booking)

    return BookingIntentResponse(
        booking=booking,  # type: ignore
        client_secret=client_secret,
    )


@router.get(
    "/",
    response_model=list[BookingResponse],
)
async def list_customer_bookings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
):
    bookings = await repository.get_customer_bookings(
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
    if not booking or booking.customer_id != current_user.id:
        raise BookingNotFoundError()
    return booking
