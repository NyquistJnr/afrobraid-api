from datetime import datetime

from pydantic import BaseModel

from app.modules.braiders.veriff.models import VeriffSessionStatus


class StartVerificationResponse(BaseModel):
    session_id: str
    verification_url: str
    status: VeriffSessionStatus


class VeriffStatusResponse(BaseModel):
    has_session: bool
    session_id: str | None = None
    verification_url: str | None = None
    status: VeriffSessionStatus | None = None
    reason: str | None = None
    reason_code: int | None = None
    acceptance_time: datetime | None = None
    submission_time: datetime | None = None
    decision_time: datetime | None = None
    is_complete: bool = False
