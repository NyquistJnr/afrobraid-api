import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import Currency
from app.core.exceptions import InvalidBookingDateRangeError
from app.core.i18n import localize_field, t
from app.core.money import from_minor_units
from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.dashboard.schemas import (
    BookingsByWeekdayResponse,
    DashboardOverviewResponse,
    RevenueTimeSeriesPoint,
    RevenueTimeSeriesResponse,
    StyleBreakdownResponse,
    StyleBreakdownSlice,
    WeekdayBreakdownPoint,
)
from app.modules.braiders import repository as braiders_repo

_DEFAULT_TIMESERIES_WINDOW_DAYS = 90
_DEFAULT_TOP_STYLES_LIMIT = 8
_ZERO = Decimal("0.00")
_HUNDRED = Decimal("100")


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_to < date_from:
        raise InvalidBookingDateRangeError()


def _percent(part: int, whole: int) -> Decimal:
    if whole == 0:
        return _ZERO
    return (Decimal(part) * _HUNDRED / Decimal(whole)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


async def get_overview(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> DashboardOverviewResponse:
    _validate_date_range(date_from, date_to)
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    if profile is None:
        return DashboardOverviewResponse(
            total_bookings=0,
            completed_bookings=0,
            upcoming_bookings=0,
            cancelled_bookings=0,
            no_show_bookings=0,
            completion_rate=_ZERO,
            cancellation_rate=_ZERO,
            total_revenue=_ZERO,
            average_booking_value=_ZERO,
            unique_customers=0,
            repeat_customers=0,
            repeat_customer_rate=_ZERO,
            average_rating=None,
            rating_count=0,
            currency=Currency.EUR,
        )

    stats = await bookings_repo.get_dashboard_overview_for_braider(
        db, profile.id, date_from=date_from, date_to=date_to
    )
    total_bookings = stats["total_bookings"]
    completed = stats["completed"]
    total_revenue = from_minor_units(stats["revenue_minor"])

    return DashboardOverviewResponse(
        total_bookings=total_bookings,
        completed_bookings=completed,
        upcoming_bookings=stats["upcoming"],
        cancelled_bookings=stats["cancelled"],
        no_show_bookings=stats["no_show"],
        completion_rate=_percent(completed, total_bookings),
        cancellation_rate=_percent(stats["cancelled"], total_bookings),
        total_revenue=total_revenue,
        average_booking_value=(total_revenue / completed).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if completed
        else _ZERO,
        unique_customers=stats["unique_customers"],
        repeat_customers=stats["repeat_customers"],
        repeat_customer_rate=_percent(stats["repeat_customers"], stats["unique_customers"]),
        average_rating=profile.average_rating,
        rating_count=profile.rating_count,
        currency=Currency.EUR,
    )


async def get_revenue_timeseries(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    date_from: date | None,
    date_to: date | None,
    interval: Literal["day", "week", "month"],
) -> RevenueTimeSeriesResponse:
    _validate_date_range(date_from, date_to)
    resolved_to = date_to or datetime.now(UTC).date()
    resolved_from = date_from or (resolved_to - timedelta(days=_DEFAULT_TIMESERIES_WINDOW_DAYS))

    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    if profile is None:
        return RevenueTimeSeriesResponse(interval=interval, currency=Currency.EUR, points=[])

    rows = await bookings_repo.get_revenue_timeseries_for_braider(
        db, profile.id, date_from=resolved_from, date_to=resolved_to, interval=interval
    )
    points = [
        RevenueTimeSeriesPoint(bucket=bucket, revenue=from_minor_units(revenue_minor), bookings_count=count)
        for bucket, revenue_minor, count in rows
    ]
    return RevenueTimeSeriesResponse(interval=interval, currency=Currency.EUR, points=points)


async def get_bookings_by_weekday(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> BookingsByWeekdayResponse:
    _validate_date_range(date_from, date_to)
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    if profile is None:
        return BookingsByWeekdayResponse(
            currency=Currency.EUR,
            points=[WeekdayBreakdownPoint(weekday=w, bookings_count=0, revenue=_ZERO) for w in range(1, 8)],
        )

    rows = await bookings_repo.get_bookings_by_weekday_for_braider(
        db, profile.id, date_from=date_from, date_to=date_to
    )
    by_weekday = {weekday: (count, revenue) for weekday, count, revenue in rows}
    points = [
        WeekdayBreakdownPoint(
            weekday=w,
            bookings_count=by_weekday.get(w, (0, _ZERO))[0],
            revenue=by_weekday.get(w, (0, _ZERO))[1],
        )
        for w in range(1, 8)
    ]
    return BookingsByWeekdayResponse(currency=Currency.EUR, points=points)


async def get_style_breakdown(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    locale: str,
    limit: int = _DEFAULT_TOP_STYLES_LIMIT,
) -> StyleBreakdownResponse:
    _validate_date_range(date_from, date_to)
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    if profile is None:
        return StyleBreakdownResponse(currency=Currency.EUR, total_revenue=_ZERO, slices=[])

    rows = await bookings_repo.get_style_breakdown_for_braider(
        db, profile.id, date_from=date_from, date_to=date_to
    )
    total_revenue = sum((revenue for _, _, _, revenue in rows), _ZERO)

    slices = [
        StyleBreakdownSlice(
            style_id=style_id,
            style_name=localize_field(style, "name", locale) or style.name_en,
            bookings_count=count,
            revenue=revenue,
            revenue_share=_percent_decimal(revenue, total_revenue),
        )
        for style_id, style, count, revenue in rows[:limit]
    ]

    if len(rows) > limit:
        other_count = sum(count for _, _, count, _ in rows[limit:])
        other_revenue = sum((revenue for _, _, _, revenue in rows[limit:]), _ZERO)
        slices.append(
            StyleBreakdownSlice(
                style_id=None,
                style_name=t("dashboard.style_other_label", locale),
                bookings_count=other_count,
                revenue=other_revenue,
                revenue_share=_percent_decimal(other_revenue, total_revenue),
            )
        )

    return StyleBreakdownResponse(currency=Currency.EUR, total_revenue=total_revenue, slices=slices)


def _percent_decimal(part: Decimal, whole: Decimal) -> Decimal:
    if whole == 0:
        return _ZERO
    return (part * _HUNDRED / whole).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
