import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.core.currency import Currency


class Dac7ReportRow(BaseModel):
    braider_id: uuid.UUID
    braider_name: str
    braider_email: str
    country: str
    currency: Currency
    booking_count: int
    gross_consideration: Decimal
    platform_fees_withheld: Decimal
    # Always null today - no collection flow exists yet (see the plan's
    # flagged item #2). Present on the row anyway so the shape is already
    # correct once that's built, rather than needing a breaking change.
    tax_identification_number: str | None = None


class Dac7ReportResponse(BaseModel):
    year: int
    quarter: int
    period_start: date
    period_end: date
    rows: list[Dac7ReportRow]
    note: str
