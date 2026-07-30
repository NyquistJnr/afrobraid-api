from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.braiders.service_location.models import LocationType

LocationTypeLiteral = Literal["HOME_STUDIO", "SALON"]

_STRIPPED_FIELDS = ("salon_name", "address_line1", "address_line2", "city", "postal_code", "country")


class ServiceLocationUpdateRequest(BaseModel):
    """Partial update - only send the fields you're changing, same as business-info.
    `location_type=null` means no fixed spot (mobile-only); `offers_mobile` is
    independent of it, so a braider can have a salon chair and travel too."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "location_type": "SALON",
                    "salon_name": "Glamour Braids Studio",
                    "address_line1": "Musterstrasse 12",
                    "city": "Berlin",
                    "postal_code": "10115",
                    "country": "DE",
                    "latitude": "52.531677",
                    "longitude": "13.381777",
                    "offers_mobile": True,
                    "travel_radius_km": 15,
                    "travel_fee": "10.00",
                }
            ]
        }
    )

    location_type: LocationTypeLiteral | None = Field(
        default=None,
        description="Null means no fixed spot - mobile-only. Required (with the "
        "address fields below) if clients come to you.",
    )
    salon_name: str | None = Field(
        default=None, max_length=150, description="Required if location_type is SALON."
    )
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, description='2-letter ISO code, e.g. "DE".')
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    offers_mobile: bool | None = Field(
        default=None, description="Independent of location_type - do you also travel to clients?"
    )
    travel_radius_km: int | None = Field(
        default=None, gt=0, le=500, description="Required if offers_mobile is true."
    )
    travel_fee: Decimal | None = Field(
        default=None, ge=0, description="Flat fee for a mobile booking. Omit or null for free."
    )

    @field_validator(*_STRIPPED_FIELDS, mode="before")
    @classmethod
    def _not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("This field cannot be blank.")
        return v

    @field_validator("country")
    @classmethod
    def _country_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) != 2 or not v.isalpha():
            raise ValueError('Country must be a 2-letter ISO code, e.g. "DE".')
        return v.upper()


class ServiceLocationResponse(BaseModel):
    location_type: LocationType | None
    salon_name: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    postal_code: str | None
    country: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    offers_mobile: bool
    travel_radius_km: int | None
    travel_fee: Decimal | None
    is_complete: bool
