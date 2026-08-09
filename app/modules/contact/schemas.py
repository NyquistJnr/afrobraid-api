import re
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.contact.enums import ContactPlatform, ContactPurpose

_MESSAGE_MAX_LENGTH = 5000
_SUBJECT_MAX_LENGTH = 255
_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


class ContactSubmissionRequest(BaseModel):
    first_name: str
    last_name: str
    phone_number: str = Field(description="E.164 format, e.g. \"+15551234567\".")
    email: EmailStr
    subject: str | None = None
    message: str
    platform: ContactPlatform = Field(description="Which app this message came from.")
    purpose: ContactPurpose = ContactPurpose.GENERAL

    @field_validator("first_name", "last_name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("This field cannot be blank.")
        return v

    @field_validator("phone_number")
    @classmethod
    def _phone_number_e164(cls, v: str) -> str:
        v = v.strip()
        if not _E164_PATTERN.match(v):
            raise ValueError("phone_number must be in E.164 format, e.g. \"+15551234567\".")
        return v

    @field_validator("subject")
    @classmethod
    def _subject_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > _SUBJECT_MAX_LENGTH:
            raise ValueError(f"Subject must be at most {_SUBJECT_MAX_LENGTH} characters long.")
        return v

    @field_validator("message")
    @classmethod
    def _message_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be blank.")
        if len(v) > _MESSAGE_MAX_LENGTH:
            raise ValueError(f"Message must be at most {_MESSAGE_MAX_LENGTH} characters long.")
        return v


class ContactSubmissionResponse(BaseModel):
    id: uuid.UUID
    message: str
