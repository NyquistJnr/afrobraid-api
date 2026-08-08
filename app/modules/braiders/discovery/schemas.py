import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.modules.braiders.models import Gender
from app.modules.braiders.service_location.models import LocationType


class MatchedStyleResponse(BaseModel):
    style_id: uuid.UUID
    name: str
    base_price: Decimal
    duration_minutes: int | None


class BraiderLocationResponse(BaseModel):
    location_type: LocationType | None
    salon_name: str | None
    address_line1: str | None
    address_line2: str | None
    postal_code: str | None
    city: str | None
    country: str | None
    # Exact for SALON, matching the address fields above. For HOME_STUDIO /
    # mobile-only braiders this is randomly fuzzed on every request (see
    # `_fuzz_coordinates` in service.py) so it doesn't reveal a home address.
    latitude: Decimal | None
    longitude: Decimal | None
    offers_mobile: bool
    travel_radius_km: int | None
    # Mandatory-charge transparency for mobile appointments (EU price
    # transparency rules require showing this pre-order, not just at
    # checkout) - also what the booking calculator needs to price a mobile
    # job before the customer commits to anything.
    travel_fee: Decimal | None


class BraiderSearchItemResponse(BaseModel):
    id: uuid.UUID
    business_name: str | None
    logo_url: str | None
    location: BraiderLocationResponse | None
    distance_km: float | None
    cover_photo_url: str | None
    matched_style: MatchedStyleResponse | None
    styles: list[MatchedStyleResponse]


class PortfolioImagePublicResponse(BaseModel):
    id: uuid.UUID
    url: str
    caption: str | None
    position: int


class BraiderStyleVariationPublicResponse(BaseModel):
    id: uuid.UUID
    name: str
    price: Decimal


class BraiderStyleAddonPublicResponse(BaseModel):
    id: uuid.UUID
    name: str
    price: Decimal
    is_required: bool


class BraiderOfferedStyleResponse(BaseModel):
    style_id: uuid.UUID
    slug: str
    name: str
    base_price: Decimal
    duration_minutes: int | None
    variations: list[BraiderStyleVariationPublicResponse]
    addons: list[BraiderStyleAddonPublicResponse]


class BraiderDetailResponse(BaseModel):
    id: uuid.UUID
    business_name: str | None
    logo_url: str | None
    bio: str | None
    gender: Gender | None
    location: BraiderLocationResponse | None
    portfolio: list[PortfolioImagePublicResponse]
    styles: list[BraiderOfferedStyleResponse]
