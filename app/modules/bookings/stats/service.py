import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidBookingDateRangeError
from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.enums import BookingStatus
from app.modules.bookings.stats.schemas import (
    BookingStatsResponse,
    BookingTimeSeriesPoint,
    BookingTimeSeriesResponse,
)
from app.modules.braiders import repository as braiders_repo

_DEFAULT_TIMESERIES_WINDOW_DAYS = 90


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_to < date_from:
        raise InvalidBookingDateRangeError()


async def get_booking_stats(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> BookingStatsResponse:
    _validate_date_range(date_from, date_to)
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    if profile is None:
        return BookingStatsResponse(total_bookings=0, completed=0, declined=0, upcoming=0)
    stats = await bookings_repo.get_booking_stats_for_braider(
        db, profile.id, date_from=date_from, date_to=date_to
    )
    return BookingStatsResponse(**stats)


async def get_booking_timeseries(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    date_from: date | None,
    date_to: date | None,
    interval: str,
    statuses: list[BookingStatus] | None,
) -> BookingTimeSeriesResponse:
    _validate_date_range(date_from, date_to)
    # No range given -> a sane default window rather than scanning the
    # braider's entire booking history every time the dashboard loads.
    resolved_to = date_to or datetime.now(UTC).date()
    resolved_from = date_from or (resolved_to - timedelta(days=_DEFAULT_TIMESERIES_WINDOW_DAYS))

    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    if profile is None:
        return BookingTimeSeriesResponse(interval=interval, statuses=statuses or [], points=[])

    rows = await bookings_repo.get_booking_timeseries_for_braider(
        db,
        profile.id,
        date_from=resolved_from,
        date_to=resolved_to,
        interval=interval,
        statuses=statuses,
    )

    points_by_bucket: dict[datetime, dict[BookingStatus, int]] = {}
    seen_statuses: set[BookingStatus] = set()
    for bucket, status, count in rows:
        points_by_bucket.setdefault(bucket, {})[status] = count
        seen_statuses.add(status)

    points = [
        BookingTimeSeriesPoint(bucket=bucket, counts=counts)
        for bucket, counts in sorted(points_by_bucket.items())
    ]
    return BookingTimeSeriesResponse(
        interval=interval,
        statuses=statuses or sorted(seen_statuses, key=lambda s: s.value),
        points=points,
    )
