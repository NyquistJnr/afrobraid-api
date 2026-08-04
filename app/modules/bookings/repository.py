import uuid
from datetime import datetime
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.bookings.calculations.models import BookingCalculation, BookingCalculationStatus
from app.modules.bookings.models import Booking


async def get_booking_by_id(db: AsyncSession, booking_id: uuid.UUID) -> Booking | None:
    stmt = (
        select(Booking)
        .where(Booking.id == booking_id)
        .options(selectinload(Booking.items), selectinload(Booking.payments))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_customer_bookings(
    db: AsyncSession, customer_id: uuid.UUID, limit: int = 50, offset: int = 0
) -> Sequence[Booking]:
    stmt = (
        select(Booking)
        .where(Booking.customer_id == customer_id)
        .order_by(Booking.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(selectinload(Booking.items), selectinload(Booking.payments))
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_braider_bookings(
    db: AsyncSession, braider_id: uuid.UUID, limit: int = 50, offset: int = 0
) -> Sequence[Booking]:
    stmt = (
        select(Booking)
        .where(Booking.braider_id == braider_id)
        .order_by(Booking.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(selectinload(Booking.items), selectinload(Booking.payments))
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def consume_calculation(
    db: AsyncSession, calculation_id: uuid.UUID, booking_id: uuid.UUID
) -> bool:
    """Atomically consumes a draft calculation. Returns True if successful."""
    stmt = (
        update(BookingCalculation)
        .where(
            BookingCalculation.id == calculation_id,
            BookingCalculation.status == BookingCalculationStatus.DRAFT,
        )
        .values(
            status=BookingCalculationStatus.CONSUMED,
            consumed_by_booking_id=booking_id,
        )
    )
    result = await db.execute(stmt)
    return result.rowcount > 0


async def get_overlapping_bookings(
    db: AsyncSession, braider_id: uuid.UUID, start_time: datetime, end_time: datetime
) -> Sequence[Booking]:
    """Returns bookings that overlap with the given time window."""
    from app.modules.bookings.enums import BookingStatus
    stmt = (
        select(Booking)
        .where(Booking.braider_id == braider_id)
        .where(
            Booking.status.in_([
                BookingStatus.PENDING_PAYMENT,
                BookingStatus.CONFIRMED,
                BookingStatus.IN_PROGRESS,
                BookingStatus.COMPLETED,
                BookingStatus.NO_SHOW,
                BookingStatus.DISPUTED,
            ])
        )
        .where(Booking.blocked_from < end_time)
        .where(Booking.blocked_until > start_time)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
