import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.users.models import UserType

_FIRST_NAME_MAX_LENGTH = 100
_LAST_NAME_MAX_LENGTH = 100
_PHONE_NUMBER_MAX_LENGTH = 32


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str | None
    email: str
    phone_number: str | None
    user_type: UserType
    chat_locale: str | None


class UserProfileUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None
    chat_locale: str | None = Field(
        default=None,
        description="Language you want to chat in (e.g. \"en\"). Required from both sides of "
        "a conversation before chat.tasks translates anything - see the chat module. Send "
        "an empty string to clear it.",
    )

    @field_validator("first_name")
    @classmethod
    def _first_name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("First name cannot be blank.")
        if len(v) > _FIRST_NAME_MAX_LENGTH:
            raise ValueError(
                f"First name must be at most {_FIRST_NAME_MAX_LENGTH} characters long."
            )
        return v

    @field_validator("last_name")
    @classmethod
    def _last_name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Last name cannot be blank.")
        if len(v) > _LAST_NAME_MAX_LENGTH:
            raise ValueError(
                f"Last name must be at most {_LAST_NAME_MAX_LENGTH} characters long."
            )
        return v

    @field_validator("phone_number")
    @classmethod
    def _phone_number_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Phone number cannot be blank.")
        if len(v) > _PHONE_NUMBER_MAX_LENGTH:
            raise ValueError(
                f"Phone number must be at most {_PHONE_NUMBER_MAX_LENGTH} characters long."
            )
        return v

    @field_validator("chat_locale")
    @classmethod
    def _chat_locale_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        return v or None
