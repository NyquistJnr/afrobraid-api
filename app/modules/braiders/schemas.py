from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.modules.braiders.models import BioSource, Gender, OnboardingStep

GenderLiteral = Literal["MALE", "FEMALE", "OTHER", "PREFER_NOT_TO_SAY"]
LogoContentType = Literal["image/jpeg", "image/png", "image/webp"]

_BUSINESS_NAME_MAX_LENGTH = 150
_BIO_MAX_LENGTH = 1000


class BusinessInfoUpdateRequest(BaseModel):
    business_name: str | None = None
    bio: str | None = None
    gender: GenderLiteral | None = None

    @field_validator("business_name")
    @classmethod
    def _business_name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Business name cannot be blank.")
        if len(v) > _BUSINESS_NAME_MAX_LENGTH:
            raise ValueError(
                f"Business name must be at most {_BUSINESS_NAME_MAX_LENGTH} characters long."
            )
        return v

    @field_validator("bio")
    @classmethod
    def _bio_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Bio cannot be blank.")
        if len(v) > _BIO_MAX_LENGTH:
            raise ValueError(f"Bio must be at most {_BIO_MAX_LENGTH} characters long.")
        return v


class BusinessInfoResponse(BaseModel):
    business_name: str | None
    logo_url: str | None
    bio_en: str | None
    bio_de: str | None
    bio_fr: str | None
    bio_en_source: BioSource | None
    bio_de_source: BioSource | None
    bio_fr_source: BioSource | None
    gender: Gender | None
    is_complete: bool


class LogoUploadUrlRequest(BaseModel):
    content_type: LogoContentType


class LogoUploadUrlResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int


class LogoConfirmRequest(BaseModel):
    object_key: str


class OnboardingStatusResponse(BaseModel):
    current_step: OnboardingStep
    business_info_completed_at: datetime | None
    veriff_completed_at: datetime | None
    service_type_completed_at: datetime | None
    portfolio_completed_at: datetime | None
    service_location_completed_at: datetime | None
    availability_completed_at: datetime | None
    payment_setup_completed_at: datetime | None
    completed_at: datetime | None
