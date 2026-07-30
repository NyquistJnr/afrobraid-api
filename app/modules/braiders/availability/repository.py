import uuid
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders.availability.models import (
    AvailabilityExceptionType,
    BraiderAvailabilityException,
    BraiderAvailabilitySettings,
    BraiderWeeklyAvailability,
    DayOfWeek,
)


async def get_settings_by_braider_id(
    db: AsyncSession, braider_id: uuid.UUID
) -> BraiderAvailabilitySettings | None:
    result = await db.execute(
        select(BraiderAvailabilitySettings).where(
            BraiderAvailabilitySettings.braider_id == braider_id
        )
    )
    return result.scalar_one_or_none()


async def create_settings_for_braider(
    db: AsyncSession, braider_id: uuid.UUID
) -> BraiderAvailabilitySettings:
    settings = BraiderAvailabilitySettings(braider_id=braider_id)
    db.add(settings)
    await db.flush()
    return settings


async def list_weekly_windows(
    db: AsyncSession, braider_id: uuid.UUID
) -> list[BraiderWeeklyAvailability]:
    result = await db.execute(
        select(BraiderWeeklyAvailability)
        .where(BraiderWeeklyAvailability.braider_id == braider_id)
        .order_by(BraiderWeeklyAvailability.day_of_week, BraiderWeeklyAvailability.start_time)
    )
    return list(result.scalars().all())


async def get_weekly_window_by_id(
    db: AsyncSession, window_id: uuid.UUID
) -> BraiderWeeklyAvailability | None:
    return await db.get(BraiderWeeklyAvailability, window_id)


async def list_weekly_windows_for_day(
    db: AsyncSession, braider_id: uuid.UUID, day_of_week: DayOfWeek, *, active_only: bool = False
) -> list[BraiderWeeklyAvailability]:
    stmt = select(BraiderWeeklyAvailability).where(
        BraiderWeeklyAvailability.braider_id == braider_id,
        BraiderWeeklyAvailability.day_of_week == day_of_week,
    )
    if active_only:
        stmt = stmt.where(BraiderWeeklyAvailability.is_active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_weekly_window(
    db: AsyncSession,
    *,
    braider_id: uuid.UUID,
    day_of_week: DayOfWeek,
    start_time: time,
    end_time: time,
) -> BraiderWeeklyAvailability:
    window = BraiderWeeklyAvailability(
        braider_id=braider_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
    )
    db.add(window)
    await db.flush()
    return window


async def delete_weekly_window(db: AsyncSession, window: BraiderWeeklyAvailability) -> None:
    await db.delete(window)
    await db.flush()


async def list_exceptions(
    db: AsyncSession,
    braider_id: uuid.UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[BraiderAvailabilityException]:
    stmt = select(BraiderAvailabilityException).where(
        BraiderAvailabilityException.braider_id == braider_id
    )
    if date_from is not None:
        stmt = stmt.where(BraiderAvailabilityException.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(BraiderAvailabilityException.date <= date_to)
    stmt = stmt.order_by(BraiderAvailabilityException.date)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_exceptions_for_date(
    db: AsyncSession, braider_id: uuid.UUID, on_date: date
) -> list[BraiderAvailabilityException]:
    result = await db.execute(
        select(BraiderAvailabilityException).where(
            BraiderAvailabilityException.braider_id == braider_id,
            BraiderAvailabilityException.date == on_date,
        )
    )
    return list(result.scalars().all())


async def get_exception_by_id(
    db: AsyncSession, exception_id: uuid.UUID
) -> BraiderAvailabilityException | None:
    return await db.get(BraiderAvailabilityException, exception_id)


async def create_exception(
    db: AsyncSession,
    *,
    braider_id: uuid.UUID,
    on_date: date,
    exception_type: AvailabilityExceptionType,
    start_time: time | None,
    end_time: time | None,
    reason: str | None,
) -> BraiderAvailabilityException:
    exception = BraiderAvailabilityException(
        braider_id=braider_id,
        date=on_date,
        exception_type=exception_type,
        start_time=start_time,
        end_time=end_time,
        reason=reason,
    )
    db.add(exception)
    await db.flush()
    return exception


async def delete_exception(db: AsyncSession, exception: BraiderAvailabilityException) -> None:
    await db.delete(exception)
    await db.flush()
