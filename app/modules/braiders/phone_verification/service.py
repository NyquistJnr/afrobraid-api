from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidVerificationCodeError,
    PhoneAlreadyExistsError,
    PhoneVerificationApiUnavailableError,
)
from app.core.rate_limit import check_rate_limit
from app.modules.braiders import repository as braiders_repo
from app.modules.braiders.completion import mark_step_complete
from app.modules.braiders.models import OnboardingStep
from app.modules.braiders.phone_verification.client import (
    TwilioVerificationError,
    check_verification_code,
    send_verification_code,
)
from app.modules.braiders.phone_verification.schemas import (
    PhoneVerificationStatusResponse,
    SendCodeRequest,
    SendCodeResponse,
    VerifyCodeRequest,
    VerifyCodeResponse,
)
from app.modules.users import repository as users_repo
from app.modules.users.models import User

_SEND_CODE_RATE_LIMIT = 5
_SEND_CODE_WINDOW_SECONDS = 3600


async def send_code(
    db: AsyncSession, redis: Redis, user: User, *, data: SendCodeRequest
) -> SendCodeResponse:
    await check_rate_limit(
        redis,
        key=f"phone_verification:{user.id}",
        limit=_SEND_CODE_RATE_LIMIT,
        window_seconds=_SEND_CODE_WINDOW_SECONDS,
    )

    existing = await users_repo.get_user_by_phone(db, data.phone_number)
    if existing and existing.id != user.id:
        raise PhoneAlreadyExistsError()

    try:
        status = await send_verification_code(data.phone_number)
    except TwilioVerificationError as exc:
        raise PhoneVerificationApiUnavailableError() from exc

    return SendCodeResponse(status=status, phone_number=data.phone_number)


async def verify_code(
    db: AsyncSession, user: User, *, data: VerifyCodeRequest
) -> VerifyCodeResponse:
    try:
        status = await check_verification_code(data.phone_number, data.code)
    except TwilioVerificationError as exc:
        raise PhoneVerificationApiUnavailableError() from exc

    if status != "approved":
        raise InvalidVerificationCodeError()

    if user.phone_number != data.phone_number:
        existing = await users_repo.get_user_by_phone(db, data.phone_number)
        if existing and existing.id != user.id:
            raise PhoneAlreadyExistsError()
        user.phone_number = data.phone_number

    onboarding_status = await braiders_repo.get_onboarding_status_by_user_id(db, user.id)
    if onboarding_status is None:
        onboarding_status = await braiders_repo.create_onboarding_status_for_user(db, user.id)
    mark_step_complete(onboarding_status, OnboardingStep.PHONE_VERIFICATION)
    await db.commit()

    return VerifyCodeResponse(status=status, is_complete=True)


async def get_status(db: AsyncSession, user: User) -> PhoneVerificationStatusResponse:
    onboarding_status = await braiders_repo.get_onboarding_status_by_user_id(db, user.id)
    is_verified = bool(
        onboarding_status and onboarding_status.phone_verification_completed_at is not None
    )
    return PhoneVerificationStatusResponse(phone_number=user.phone_number, is_verified=is_verified)
