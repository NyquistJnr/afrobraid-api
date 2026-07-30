import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PortfolioImageContentType = Literal["image/jpeg", "image/png", "image/webp"]

_CAPTION_MAX_LENGTH = 300


def _caption_valid(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip()
    if not v:
        raise ValueError("Caption cannot be blank.")
    if len(v) > _CAPTION_MAX_LENGTH:
        raise ValueError(f"Caption must be at most {_CAPTION_MAX_LENGTH} characters long.")
    return v


class PortfolioImageResponse(BaseModel):
    id: uuid.UUID
    url: str
    caption: str | None
    position: int


class PortfolioResponse(BaseModel):
    images: list[PortfolioImageResponse]
    min_required: int
    is_complete: bool


class PortfolioImageUploadUrlRequest(BaseModel):
    content_type: PortfolioImageContentType


class PortfolioImageUploadUrlResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int


class PortfolioImageConfirmRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "object_key": "braiders/<your-user-id>/portfolio/<uuid>.jpg",
                    "caption": "Knotless braids, waist length - 4 hours",
                }
            ]
        }
    )

    object_key: str = Field(
        description="The `object_key` returned by the upload-url step above - "
        "not a file path or URL of your own."
    )
    caption: str | None = Field(
        default=None, description="Optional, shown to clients alongside the photo."
    )

    @field_validator("caption")
    @classmethod
    def _caption_valid(cls, v: str | None) -> str | None:
        return _caption_valid(v)


class PortfolioImageUpdateRequest(BaseModel):
    caption: str | None = None

    @field_validator("caption")
    @classmethod
    def _caption_valid(cls, v: str | None) -> str | None:
        return _caption_valid(v)
