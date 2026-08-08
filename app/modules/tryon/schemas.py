import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.tryon.models import TryOnStatus

TryOnImageContentType = Literal["image/jpeg", "image/png", "image/webp"]

_DESCRIPTION_MAX_LENGTH = 500


class TryOnUploadUrlRequest(BaseModel):
    content_type: TryOnImageContentType


class TryOnUploadUrlResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int


class TryOnCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "object_key": "tryon/<your-user-id>/original/<uuid>.jpg",
                    "style_id": "<a style id from GET /api/v1/styles>",
                    "style_variation_id": None,
                    "description": "shoulder length, honey blonde highlights",
                }
            ]
        }
    )

    object_key: str = Field(
        description="The `object_key` returned by the upload-url step above - "
        "not a file path or URL of your own."
    )
    style_id: uuid.UUID | None = Field(
        default=None, description="A style from GET /api/v1/styles, if the client picked one."
    )
    style_variation_id: uuid.UUID | None = Field(
        default=None, description="Must belong to `style_id` if sent."
    )
    description: str | None = Field(
        default=None,
        description="Free-text description of the desired hairstyle, e.g. 'shoulder "
        "length, honey blonde highlights'. Combined with the selected style (if any) "
        "to build the prompt sent to the model - send either a style, a description, "
        "or both for the best result.",
    )

    @field_validator("description")
    @classmethod
    def _description_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > _DESCRIPTION_MAX_LENGTH:
            raise ValueError(
                f"Description must be at most {_DESCRIPTION_MAX_LENGTH} characters long."
            )
        return v


class TryOnStyleSummary(BaseModel):
    id: uuid.UUID
    slug: str
    name: str


class TryOnStyleVariationSummary(BaseModel):
    id: uuid.UUID
    name: str


class TryOnResponse(BaseModel):
    id: uuid.UUID
    status: TryOnStatus
    style: TryOnStyleSummary | None
    style_variation: TryOnStyleVariationSummary | None
    description: str | None
    result_url: str | None
    error_message: str | None
    created_at: datetime
