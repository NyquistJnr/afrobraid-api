import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.styles.models import TranslationSource

StyleImageContentType = Literal["image/jpeg", "image/png", "image/webp"]

_NAME_MAX_LENGTH = 150
_DESCRIPTION_MAX_LENGTH = 2000


def _required_not_blank(v: str, *, field_label: str, max_length: int) -> str:
    v = v.strip()
    if not v:
        raise ValueError(f"{field_label} cannot be blank.")
    if len(v) > max_length:
        raise ValueError(f"{field_label} must be at most {max_length} characters long.")
    return v


def _not_blank(v: str | None, *, field_label: str, max_length: int) -> str | None:
    if v is None:
        return v
    return _required_not_blank(v, field_label=field_label, max_length=max_length)


class StyleCategoryCreateRequest(BaseModel):
    name: str
    display_order: int = 0

    @field_validator("name")
    @classmethod
    def _name_valid(cls, v: str) -> str:
        return _required_not_blank(v, field_label="Name", max_length=_NAME_MAX_LENGTH)


class StyleCategoryUpdateRequest(BaseModel):
    name: str | None = None
    display_order: int | None = None

    @field_validator("name")
    @classmethod
    def _name_valid(cls, v: str | None) -> str | None:
        return _not_blank(v, field_label="Name", max_length=_NAME_MAX_LENGTH)


class StyleCategoryResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name_en: str
    name_de: str | None
    name_fr: str | None
    name_en_source: TranslationSource | None
    name_de_source: TranslationSource | None
    name_fr_source: TranslationSource | None
    display_order: int


class StyleCreateRequest(BaseModel):
    category_id: uuid.UUID | None = None
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def _name_valid(cls, v: str) -> str:
        return _required_not_blank(v, field_label="Name", max_length=_NAME_MAX_LENGTH)

    @field_validator("description")
    @classmethod
    def _description_valid(cls, v: str | None) -> str | None:
        return _not_blank(v, field_label="Description", max_length=_DESCRIPTION_MAX_LENGTH)


class StyleUpdateRequest(BaseModel):
    category_id: uuid.UUID | None = None
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _name_valid(cls, v: str | None) -> str | None:
        return _not_blank(v, field_label="Name", max_length=_NAME_MAX_LENGTH)

    @field_validator("description")
    @classmethod
    def _description_valid(cls, v: str | None) -> str | None:
        return _not_blank(v, field_label="Description", max_length=_DESCRIPTION_MAX_LENGTH)


class StyleImageResponse(BaseModel):
    id: uuid.UUID
    url: str
    position: int


class StyleVariationCreateRequest(BaseModel):
    name: str
    display_order: int = 0

    @field_validator("name")
    @classmethod
    def _name_valid(cls, v: str) -> str:
        return _required_not_blank(v, field_label="Name", max_length=_NAME_MAX_LENGTH)


class StyleVariationUpdateRequest(BaseModel):
    name: str | None = None
    display_order: int | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _name_valid(cls, v: str | None) -> str | None:
        return _not_blank(v, field_label="Name", max_length=_NAME_MAX_LENGTH)


class StyleVariationResponse(BaseModel):
    id: uuid.UUID
    name_en: str
    name_de: str | None
    name_fr: str | None
    name_en_source: TranslationSource | None
    name_de_source: TranslationSource | None
    name_fr_source: TranslationSource | None
    display_order: int
    is_active: bool


class StyleResponse(BaseModel):
    id: uuid.UUID
    slug: str
    category_id: uuid.UUID | None
    name_en: str
    name_de: str | None
    name_fr: str | None
    name_en_source: TranslationSource | None
    name_de_source: TranslationSource | None
    name_fr_source: TranslationSource | None
    description_en: str | None
    description_de: str | None
    description_fr: str | None
    description_en_source: TranslationSource | None
    description_de_source: TranslationSource | None
    description_fr_source: TranslationSource | None
    is_active: bool
    images: list[StyleImageResponse]
    variations: list[StyleVariationResponse]


class StyleCategoryPublicResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    display_order: int


class StyleVariationPublicResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_order: int
    is_active: bool


class StylePublicResponse(BaseModel):
    id: uuid.UUID
    slug: str
    category_id: uuid.UUID | None
    name: str
    description: str | None
    is_active: bool
    images: list[StyleImageResponse]
    variations: list[StyleVariationPublicResponse]


class AddOnPublicResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    suggested_price: Decimal | None
    is_active: bool


class StyleImageUploadUrlRequest(BaseModel):
    content_type: StyleImageContentType


class StyleImageUploadUrlResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int


class StyleImageConfirmRequest(BaseModel):
    object_key: str


class AddOnCreateRequest(BaseModel):
    name: str
    suggested_price: Decimal | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def _name_valid(cls, v: str) -> str:
        return _required_not_blank(v, field_label="Name", max_length=_NAME_MAX_LENGTH)


class AddOnUpdateRequest(BaseModel):
    name: str | None = None
    suggested_price: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _name_valid(cls, v: str | None) -> str | None:
        return _not_blank(v, field_label="Name", max_length=_NAME_MAX_LENGTH)


class AddOnResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name_en: str
    name_de: str | None
    name_fr: str | None
    name_en_source: TranslationSource | None
    name_de_source: TranslationSource | None
    name_fr_source: TranslationSource | None
    suggested_price: Decimal | None
    is_active: bool
