import re

from pydantic import BaseModel, field_validator

_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


def _validate_e164(v: str) -> str:
    v = v.strip()
    if not _E164_PATTERN.match(v):
        raise ValueError("Phone number must be in E.164 format, e.g. +15551234567.")
    return v


class SendCodeRequest(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def _phone_number_e164(cls, v: str) -> str:
        return _validate_e164(v)


class SendCodeResponse(BaseModel):
    status: str
    phone_number: str


class VerifyCodeRequest(BaseModel):
    phone_number: str
    code: str

    @field_validator("phone_number")
    @classmethod
    def _phone_number_e164(cls, v: str) -> str:
        return _validate_e164(v)


class VerifyCodeResponse(BaseModel):
    status: str
    is_complete: bool


class PhoneVerificationStatusResponse(BaseModel):
    phone_number: str | None
    is_verified: bool
