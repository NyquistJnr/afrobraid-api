import re
from typing import Literal

from pydantic import BaseModel, EmailStr, field_validator

from app.modules.users.schemas import UserPublic

SignupUserType = Literal["CUSTOMER", "BRAIDER"]

_PASSWORD_MIN_LENGTH = 8


def _validate_password_strength(value: str) -> str:
    if len(value) < _PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {_PASSWORD_MIN_LENGTH} characters long.")
    if not re.search(r"[A-Za-z]", value):
        raise ValueError("Password must contain at least one letter.")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one number.")
    return value


class SignupEmailRequest(BaseModel):
    first_name: str
    last_name: str | None = None
    email: EmailStr
    phone_number: str | None = None
    password: str
    user_type: SignupUserType

    @field_validator("first_name")
    @classmethod
    def _first_name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("First name is required.")
        return v

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SocialLoginRequest(BaseModel):
    provider_token: str
    user_type: SignupUserType | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class SignupResponse(BaseModel):
    message: str
    email: EmailStr


class MessageResponse(BaseModel):
    message: str


class AuthTokenResponse(UserPublic):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
