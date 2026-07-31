import json
import uuid
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import VeriffApiUnavailableError, VeriffSessionNotFoundError
from app.core.rate_limit import check_rate_limit
from app.modules.braiders import repository as braiders_repo
from app.modules.braiders.completion import mark_step_complete
from app.modules.braiders.models import OnboardingStep
from app.modules.braiders.veriff import repository as veriff_repo
from app.modules.braiders.veriff.client import VeriffApiError, create_session, get_decision
from app.modules.braiders.veriff.models import VeriffSession, VeriffSessionStatus
from app.modules.braiders.veriff.schemas import StartVerificationResponse, VeriffStatusResponse
from app.modules.users.models import User

_START_SESSION_RATE_LIMIT = 5
_START_SESSION_WINDOW_SECONDS = 3600


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


async def _apply_decision(
    db: AsyncSession, session: VeriffSession, verification: dict[str, Any]
) -> None:
    session.status = VeriffSessionStatus(verification["status"].upper())
    session.decision_code = verification.get("code")
    session.reason = verification.get("reason")
    session.reason_code = verification.get("reasonCode")
    session.acceptance_time = _parse_time(verification.get("acceptanceTime"))
    session.submission_time = _parse_time(verification.get("submissionTime"))
    session.decision_time = _parse_time(verification.get("decisionTime"))
    session.last_webhook_payload = json.dumps(verification)
    await db.flush()

    if session.status == VeriffSessionStatus.APPROVED:
        status = await braiders_repo.get_onboarding_status_by_user_id(db, session.user_id)
        if status is None:
            status = await braiders_repo.create_onboarding_status_for_user(db, session.user_id)
        mark_step_complete(status, OnboardingStep.VERIFF)

    await db.commit()


def _to_status_response(session: VeriffSession | None) -> VeriffStatusResponse:
    if session is None:
        return VeriffStatusResponse(has_session=False)
    return VeriffStatusResponse(
        has_session=True,
        session_id=session.veriff_session_id,
        verification_url=session.verification_url,
        status=session.status,
        reason=session.reason,
        reason_code=session.reason_code,
        acceptance_time=session.acceptance_time,
        submission_time=session.submission_time,
        decision_time=session.decision_time,
        is_complete=session.status == VeriffSessionStatus.APPROVED,
    )


async def start_verification(
    db: AsyncSession, redis: Redis, user: User
) -> StartVerificationResponse:
    await check_rate_limit(
        redis,
        key=f"veriff_session:{user.id}",
        limit=_START_SESSION_RATE_LIMIT,
        window_seconds=_START_SESSION_WINDOW_SECONDS,
    )

    try:
        result = await create_session(
            first_name=user.first_name, last_name=user.last_name or "", vendor_data=str(user.id)
        )
    except VeriffApiError as exc:
        raise VeriffApiUnavailableError() from exc

    status_enum = VeriffSessionStatus(result.status.upper())
    session = await veriff_repo.create_session_record(
        db,
        user_id=user.id,
        veriff_session_id=result.session_id,
        verification_url=result.verification_url,
        status=status_enum,
    )
    await db.commit()

    return StartVerificationResponse(
        session_id=session.veriff_session_id,
        verification_url=session.verification_url or "",
        status=session.status,
    )


async def get_status(db: AsyncSession, user_id: uuid.UUID) -> VeriffStatusResponse:
    session = await veriff_repo.get_latest_session_by_user_id(db, user_id)
    return _to_status_response(session)


async def refresh_status(db: AsyncSession, user_id: uuid.UUID) -> VeriffStatusResponse:
    session = await veriff_repo.get_latest_session_by_user_id(db, user_id)
    if session is None:
        raise VeriffSessionNotFoundError()

    try:
        verification = await get_decision(session.veriff_session_id)
    except VeriffApiError as exc:
        raise VeriffApiUnavailableError() from exc

    if verification is not None:
        await _apply_decision(db, session, verification)

    return _to_status_response(session)


async def handle_webhook(db: AsyncSession, payload: dict[str, Any]) -> None:
    verification = payload.get("verification")
    if not verification or not verification.get("id"):
        return

    session = await veriff_repo.get_session_by_veriff_id(db, verification["id"])
    if session is None:
        return

    await _apply_decision(db, session, verification)
