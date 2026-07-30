import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class BraiderStyleVariationInput(BaseModel):
    style_variation_id: uuid.UUID
    price: Decimal = Field(gt=0)


class BraiderStyleAddonInput(BaseModel):
    addon_id: uuid.UUID
    price: Decimal = Field(ge=0)
    is_required: bool = False


class BraiderStyleCreateRequest(BaseModel):
    style_id: uuid.UUID
    base_price: Decimal = Field(gt=0)
    duration_minutes: int | None = Field(default=None, gt=0)
    variations: list[BraiderStyleVariationInput] = []
    addons: list[BraiderStyleAddonInput] = []


class BraiderStyleUpdateRequest(BaseModel):
    base_price: Decimal | None = Field(default=None, gt=0)
    duration_minutes: int | None = Field(default=None, gt=0)
    is_active: bool | None = None
    variations: list[BraiderStyleVariationInput] | None = None
    addons: list[BraiderStyleAddonInput] | None = None


class BraiderStyleVariationResponse(BaseModel):
    id: uuid.UUID
    style_variation_id: uuid.UUID
    name_en: str
    name_de: str | None
    name_fr: str | None
    price: Decimal


class BraiderStyleAddonResponse(BaseModel):
    id: uuid.UUID
    addon_id: uuid.UUID
    name_en: str
    name_de: str | None
    name_fr: str | None
    price: Decimal
    is_required: bool


class BraiderStyleResponse(BaseModel):
    id: uuid.UUID
    style_id: uuid.UUID
    style_slug: str
    style_name_en: str
    style_name_de: str | None
    style_name_fr: str | None
    primary_image_url: str | None
    base_price: Decimal
    duration_minutes: int | None
    is_active: bool
    variations: list[BraiderStyleVariationResponse]
    addons: list[BraiderStyleAddonResponse]
