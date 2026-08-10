from datetime import datetime

from pydantic import BaseModel

from app.modules.bookings.enums import BookingStatus


class BookingStatsResponse(BaseModel):
    """The four numbers on a braider's booking-stats tile. Deliberately
    capped at this set rather than exposing every BookingStatus count - see
    DECLINED_BOOKING_STATUSES / UPCOMING_BOOKING_STATUSES in
    app.modules.bookings.enums for what "declined" and "upcoming" group
    together."""

    total_bookings: int
    completed: int
    declined: int
    upcoming: int


class BookingTimeSeriesPoint(BaseModel):
    bucket: datetime
    counts: dict[BookingStatus, int]


class BookingTimeSeriesResponse(BaseModel):
    interval: str
    statuses: list[BookingStatus]
    points: list[BookingTimeSeriesPoint]
