import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.braiders.models import BioSource
from app.modules.reviews.models import ReviewStatus

_COMMENT_MAX_LENGTH = 1000


class ReviewUpsertRequest(BaseModel):
    rating: int = Field(ge=1, le=5, description="1 to 5 stars.")
    comment: str | None = Field(
        default=None,
        description="Optional written review. Write it in whichever language you're using "
        "right now (set via `?lang=` or Accept-Language) - it's saved as that locale's "
        "text and the other two are auto-translated. Needs admin approval before it's "
        "publicly visible; the rating itself counts immediately regardless. Send `null` "
        "to remove your comment (the rating stays).",
    )

    @field_validator("comment")
    @classmethod
    def _comment_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > _COMMENT_MAX_LENGTH:
            raise ValueError(f"Comment must be at most {_COMMENT_MAX_LENGTH} characters long.")
        return v


class ReviewResponse(BaseModel):
    id: uuid.UUID
    braider_id: uuid.UUID
    rating: int
    comment_en: str | None
    comment_de: str | None
    comment_fr: str | None
    comment_en_source: BioSource | None
    comment_de_source: BioSource | None
    comment_fr_source: BioSource | None
    status: ReviewStatus
    created_at: datetime
    updated_at: datetime


class PublicReviewResponse(BaseModel):
    id: uuid.UUID
    customer_name: str
    rating: int
    comment: str | None
    created_at: datetime
    updated_at: datetime


class AdminReviewResponse(BaseModel):
    id: uuid.UUID
    braider_id: uuid.UUID
    braider_name: str
    customer_id: uuid.UUID
    customer_name: str
    rating: int
    comment_en: str | None
    comment_de: str | None
    comment_fr: str | None
    status: ReviewStatus
    created_at: datetime
    updated_at: datetime
