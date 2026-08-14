from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidDac7QuarterError
from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.dac7.schemas import Dac7ReportResponse, Dac7ReportRow
from app.modules.braiders import repository as braiders_repo

_QUARTER_MONTHS = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}

_NOTE = (
    "Draft aggregation only - not a submission-ready DAC7/PStTG filing. "
    "Braider tax identification numbers are not yet collected (every row "
    "shows null); reportable-seller thresholds (30 activities or EUR 2,000 "
    "gross consideration per seller per year) are not yet applied - this "
    "returns every braider with qualifying activity in the period. Get a "
    "tax advisor to review before this is used for an actual filing."
)


def _quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    if quarter not in _QUARTER_MONTHS:
        raise InvalidDac7QuarterError()
    start_month, end_month = _QUARTER_MONTHS[quarter]
    period_start = date(year, start_month, 1)
    if end_month == 12:
        period_end_exclusive = date(year + 1, 1, 1)
    else:
        period_end_exclusive = date(year, end_month + 1, 1)
    return period_start, period_end_exclusive


async def generate_report(db: AsyncSession, *, year: int, quarter: int) -> Dac7ReportResponse:
    """Design correction #14's DAC7 flag, made queryable: per (braider,
    country, currency), every COMPLETED/NO_SHOW booking whose `ends_at`
    (when the service was actually rendered) falls in the given quarter -
    gross consideration (the braider's share) and platform fees withheld,
    which is what §14 UStG / DAC7 asks a marketplace to report per seller
    per period. Deliberately a report, not a filing pipeline - see _NOTE.
    """
    period_start, period_end_exclusive = _quarter_bounds(year, quarter)
    start_dt = datetime.combine(period_start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(period_end_exclusive, time.min, tzinfo=UTC)

    aggregates = await bookings_repo.get_dac7_aggregates(db, period_start=start_dt, period_end=end_dt)

    braider_ids = list({row.braider_id for row in aggregates})
    contact_info = await braiders_repo.list_contact_info(db, braider_ids)

    rows = [
        Dac7ReportRow(
            braider_id=row.braider_id,
            braider_name=contact_info.get(row.braider_id, {}).get("name", ""),
            braider_email=contact_info.get(row.braider_id, {}).get("email", ""),
            country=row.country,
            currency=row.currency,
            booking_count=row.booking_count,
            gross_consideration=row.gross_consideration,
            platform_fees_withheld=row.platform_fees_withheld,
            tax_identification_number=None,
        )
        for row in aggregates
    ]

    return Dac7ReportResponse(
        year=year,
        quarter=quarter,
        period_start=period_start,
        period_end=period_end_exclusive - timedelta(days=1),
        rows=rows,
        note=_NOTE,
    )
