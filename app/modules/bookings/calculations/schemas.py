import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.currency import Currency
from app.modules.bookings.calculations.models import BookingCalculationStatus
from app.modules.bookings.enums import BookingItemType


class BookingCalculationInput(BaseModel):
    braider_id: uuid.UUID
    style_id: uuid.UUID
    # Both variation and add-on ids are the braider-scoped join-row ids
    # (braider_style_variations.id / braider_style_addons.id) - the same
    # ids already returned by GET /api/v1/braiders/{id}, not the catalog
    # style_variations.id/addons.id. This makes the id unambiguous about
    # *which braider's* pricing it refers to.
    braider_style_variation_id: uuid.UUID | None = None
    braider_style_addon_ids: list[uuid.UUID] = Field(default_factory=list)
    is_mobile: bool = False


class BookingCalculationUpdateRequest(BaseModel):
    braider_id: uuid.UUID | None = None
    style_id: uuid.UUID | None = None
    braider_style_variation_id: uuid.UUID | None = None
    braider_style_addon_ids: list[uuid.UUID] | None = None
    is_mobile: bool | None = None


class BookingCalculationLineResponse(BaseModel):
    item_type: BookingItemType
    name: str | None = None
    quantity: int = 1
    unit_amount: Decimal
    line_amount: Decimal
    is_required: bool = False


class BookingCalculationPreviewResponse(BaseModel):
    currency: Currency
    braider_id: uuid.UUID
    style_id: uuid.UUID
    style_name: str
    duration_minutes: int
    is_mobile: bool
    items: list[BookingCalculationLineResponse]
    service_subtotal: Decimal
    travel_fee: Decimal
    subtotal: Decimal
    platform_fee: Decimal
    vat_on_service: Decimal
    vat_on_platform_fee: Decimal
    vat_total: Decimal
    total: Decimal
    deposit_amount: Decimal
    balance_amount: Decimal
    deposit_note: str


class BookingCalculationResponse(BookingCalculationPreviewResponse):
    id: uuid.UUID
    status: BookingCalculationStatus
    expires_at: datetime
