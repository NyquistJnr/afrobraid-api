import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EXAMPLE_VARIATION_ID = "1eeef850-0d5d-46b6-9e7f-057f724ab925"
_EXAMPLE_ADDON_ID = "cc35d230-d447-4522-aec7-db69d34a855a"
_EXAMPLE_STYLE_ID = "6e3f0a0c-bb9f-4715-ae93-da95b0e9b9ce"
_EXAMPLE_BRAIDER_STYLE_ID = "8d416c5e-57ed-4597-a587-326807a96277"


def _reject_bare_ids(v: Any, *, field_name: str, id_field: str, example: str) -> Any:
    """Pydantic's default error for `["<uuid>"]` where a list of objects is
    expected ("Input should be a valid dictionary") doesn't say what to send
    instead - this catches that specific mistake with an actionable message."""
    if isinstance(v, list) and any(isinstance(item, str) for item in v):
        raise ValueError(
            f'Each "{field_name}" entry must be an object like '
            f'{{"{id_field}": "{example}", "price": "..."}}, not a bare ID string.'
        )
    return v


class BraiderStyleVariationInput(BaseModel):
    """One priced size/length option. `style_variation_id` alone is not
    enough - it must be wrapped in this object together with your price,
    not passed as a bare string in the `variations` array."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"style_variation_id": _EXAMPLE_VARIATION_ID, "price": "200.00"}]
        }
    )

    style_variation_id: uuid.UUID = Field(
        description="A variation ID that belongs to `style_id` - copy one from "
        "GET /api/v1/styles/{style_id}'s `variations` array."
    )
    price: Decimal = Field(gt=0, description="Your price for this variation, e.g. \"200.00\".")


class BraiderStyleAddonInput(BaseModel):
    """One priced add-on. `addon_id` alone is not enough - it must be wrapped
    in this object together with your price, not passed as a bare string in
    the `addons` array."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"addon_id": _EXAMPLE_ADDON_ID, "price": "20.00", "is_required": False}]
        }
    )

    addon_id: uuid.UUID = Field(
        description="An add-on ID - copy one from GET /api/v1/addons."
    )
    price: Decimal = Field(ge=0, description="Your price for this add-on, e.g. \"20.00\".")
    is_required: bool = Field(
        default=False,
        description="If true, this add-on is always included and priced in "
        "(e.g. a mandatory pre-braid wash) rather than an optional upsell.",
    )


class BraiderStyleCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "style_id": _EXAMPLE_STYLE_ID,
                    "base_price": "180.00",
                    "duration_minutes": 240,
                    "variations": [
                        {"style_variation_id": _EXAMPLE_VARIATION_ID, "price": "200.00"}
                    ],
                    "addons": [
                        {
                            "addon_id": _EXAMPLE_ADDON_ID,
                            "price": "20.00",
                            "is_required": False,
                        }
                    ],
                }
            ]
        }
    )

    style_id: uuid.UUID = Field(
        description="A published style ID - copy one from GET /api/v1/styles."
    )
    base_price: Decimal = Field(gt=0, description="Your base price for this style, e.g. \"180.00\".")
    duration_minutes: int | None = Field(default=None, gt=0)
    variations: list[BraiderStyleVariationInput] = Field(
        default=[],
        description="Optional. Each entry is an object - "
        '{"style_variation_id": "...", "price": "..."} - not just the ID string. '
        "Leave empty ([]) if this style has no variations you want to offer.",
    )
    addons: list[BraiderStyleAddonInput] = Field(
        default=[],
        description="Optional. Each entry is an object - "
        '{"addon_id": "...", "price": "..."} - not just the ID string. '
        "Leave empty ([]) if you don't offer any add-ons for this style.",
    )

    @field_validator("variations", mode="before")
    @classmethod
    def _variations_shape(cls, v: Any) -> Any:
        return _reject_bare_ids(
            v,
            field_name="variations",
            id_field="style_variation_id",
            example=_EXAMPLE_VARIATION_ID,
        )

    @field_validator("addons", mode="before")
    @classmethod
    def _addons_shape(cls, v: Any) -> Any:
        return _reject_bare_ids(
            v, field_name="addons", id_field="addon_id", example=_EXAMPLE_ADDON_ID
        )


class BraiderStyleUpdateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"base_price": "190.00"}]}
    )

    base_price: Decimal | None = Field(default=None, gt=0)
    duration_minutes: int | None = Field(default=None, gt=0)
    is_active: bool | None = None
    variations: list[BraiderStyleVariationInput] | None = Field(
        default=None,
        description="Optional. If provided, this fully replaces the existing "
        "variation list - send all the ones you still want, not just new ones.",
    )
    addons: list[BraiderStyleAddonInput] | None = Field(
        default=None,
        description="Optional. If provided, this fully replaces the existing "
        "add-on list - send all the ones you still want, not just new ones.",
    )

    @field_validator("variations", mode="before")
    @classmethod
    def _variations_shape(cls, v: Any) -> Any:
        return _reject_bare_ids(
            v,
            field_name="variations",
            id_field="style_variation_id",
            example=_EXAMPLE_VARIATION_ID,
        )

    @field_validator("addons", mode="before")
    @classmethod
    def _addons_shape(cls, v: Any) -> Any:
        return _reject_bare_ids(
            v, field_name="addons", id_field="addon_id", example=_EXAMPLE_ADDON_ID
        )


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
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": _EXAMPLE_BRAIDER_STYLE_ID,
                    "style_id": _EXAMPLE_STYLE_ID,
                    "style_slug": "knotless-braids-mid-back",
                    "style_name_en": "Knotless Braids - Mid Back",
                    "style_name_de": "Knotless Braids - Mittellang",
                    "style_name_fr": "Tresses Knotless - Mi-Dos",
                    "primary_image_url": None,
                    "base_price": "180.00",
                    "duration_minutes": 240,
                    "is_active": True,
                    "variations": [
                        {
                            "id": "86538614-9cd8-4715-9ec1-6c36c8d93937",
                            "style_variation_id": _EXAMPLE_VARIATION_ID,
                            "name_en": "Mid-back length",
                            "name_de": "Rückenlang (Mitte)",
                            "name_fr": "Longueur Mi-Dos",
                            "price": "200.00",
                        }
                    ],
                    "addons": [
                        {
                            "id": "be5f5561-76e0-4339-bb18-7c75e1d441fb",
                            "addon_id": _EXAMPLE_ADDON_ID,
                            "name_en": "Beads",
                            "name_de": "Perlen",
                            "name_fr": "Perles",
                            "price": "20.00",
                            "is_required": False,
                        }
                    ],
                }
            ]
        }
    )

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
