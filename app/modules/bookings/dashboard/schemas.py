import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.core.currency import Currency


class DashboardOverviewResponse(BaseModel):
    total_bookings: int
    completed_bookings: int
    upcoming_bookings: int
    cancelled_bookings: int
    no_show_bookings: int
    completion_rate: Decimal
    cancellation_rate: Decimal
    total_revenue: Decimal
    average_booking_value: Decimal
    unique_customers: int
    repeat_customers: int
    repeat_customer_rate: Decimal
    average_rating: Decimal | None
    rating_count: int
    currency: Currency


class RevenueTimeSeriesPoint(BaseModel):
    bucket: datetime
    revenue: Decimal
    bookings_count: int


class RevenueTimeSeriesResponse(BaseModel):
    interval: str
    currency: Currency
    points: list[RevenueTimeSeriesPoint]


class WeekdayBreakdownPoint(BaseModel):
    weekday: int
    bookings_count: int
    revenue: Decimal


class BookingsByWeekdayResponse(BaseModel):
    currency: Currency
    points: list[WeekdayBreakdownPoint]


class StyleBreakdownSlice(BaseModel):
    style_id: uuid.UUID | None
    style_name: str
    bookings_count: int
    revenue: Decimal
    revenue_share: Decimal


class StyleBreakdownResponse(BaseModel):
    currency: Currency
    total_revenue: Decimal
    slices: list[StyleBreakdownSlice]
