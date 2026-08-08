import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.chat.models import ChatMessageStatus, ChatReportReason, ChatReportStatus

_MESSAGE_MAX_LENGTH = 2000
_REPORT_DETAILS_MAX_LENGTH = 1000


class ChatMessageCreateRequest(BaseModel):
    body: str = Field(description="The message text, in whichever language you're chatting in.")

    @field_validator("body")
    @classmethod
    def _body_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message can't be empty.")
        if len(v) > _MESSAGE_MAX_LENGTH:
            raise ValueError(f"Message must be at most {_MESSAGE_MAX_LENGTH} characters long.")
        return v


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    sender_id: uuid.UUID
    status: ChatMessageStatus
    body: str | None = Field(description="Null when `status` is FLAGGED - see `violation_notice`.")
    body_locale: str | None
    translated_body: str | None = Field(
        description="Populated once translation finishes, only when both participants had set "
        "a different `chat_locale` on their profile - null otherwise, including for FLAGGED messages."
    )
    translated_locale: str | None
    violation_notice: str | None = Field(
        default=None, description="Localized policy notice shown in place of the real content when flagged."
    )
    created_at: datetime


class ChatThreadResponse(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    other_participant_id: uuid.UUID
    other_participant_name: str
    last_message_at: datetime | None
    last_message_preview: str | None
    last_message_flagged: bool
    unread_count: int
    created_at: datetime


class ChatReportCreateRequest(BaseModel):
    reason: ChatReportReason
    details: str | None = Field(default=None, description="Optional free-text details about what happened.")
    message_id: uuid.UUID | None = Field(
        default=None, description="Optional - the specific message this report is about, if any."
    )

    @field_validator("details")
    @classmethod
    def _details_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > _REPORT_DETAILS_MAX_LENGTH:
            raise ValueError(f"Details must be at most {_REPORT_DETAILS_MAX_LENGTH} characters long.")
        return v


class ChatReportResponse(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    reported_user_id: uuid.UUID
    reason: ChatReportReason
    status: ChatReportStatus
    created_at: datetime


class AdminChatReportUpdateRequest(BaseModel):
    status: ChatReportStatus
    admin_notes: str | None = None

    @field_validator("admin_notes")
    @classmethod
    def _admin_notes_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None


class AdminChatReportResponse(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    booking_id: uuid.UUID
    reporter_id: uuid.UUID
    reporter_name: str
    reported_user_id: uuid.UUID
    reported_user_name: str
    message_id: uuid.UUID | None
    reason: ChatReportReason
    details: str | None
    status: ChatReportStatus
    admin_notes: str | None
    created_at: datetime
    updated_at: datetime
