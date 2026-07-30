from datetime import UTC, datetime

from arq import ArqRedis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    EmailAlreadyExistsError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidOtpError,
    InvalidRefreshTokenError,
    OtpExpiredError,
    PhoneAlreadyExistsError,
    SocialAuthError,
    TooManyOtpAttemptsError,
    UserNotActiveError,
    UserTypeRequiredError,
)
from app.core.i18n import t
from app.core.rate_limit import check_rate_limit
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    generate_otp_code,
    hash_password,
    hash_token,
    verify_password,
)
from app.modules.auth import repository as auth_repo
from app.modules.auth.models import OtpPurpose
from app.modules.auth.schemas import (
    AuthTokenResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SignupEmailRequest,
    SignupResponse,
    SocialLoginRequest,
    VerifyEmailRequest,
)
from app.modules.auth.social import verify_social_token
from app.modules.auth.tasks import TASK_SEND_OTP_EMAIL
from app.modules.users import repository as users_repo
from app.modules.users.models import AuthProvider, User, UserType

settings = get_settings()

MAX_OTP_ATTEMPTS = 5


async def _issue_token_pair(
    db: AsyncSession, user: User, *, remember_me: bool = False
) -> tuple[str, str, int]:
    access_expire_minutes = (
        settings.remember_me_access_token_expire_minutes
        if remember_me
        else settings.access_token_expire_minutes
    )
    refresh_expire_days = (
        settings.remember_me_refresh_token_expire_days
        if remember_me
        else settings.refresh_token_expire_days
    )

    access_token, _jti = create_access_token(
        user_id=user.id, user_type=user.user_type.value, expire_minutes=access_expire_minutes
    )
    raw_refresh_token = generate_opaque_token()
    await auth_repo.create_refresh_token(
        db,
        user_id=user.id,
        token_hash=hash_token(raw_refresh_token),
        expire_days=refresh_expire_days,
        remember_me=remember_me,
    )
    expires_in = access_expire_minutes * 60
    return access_token, raw_refresh_token, expires_in


def _to_auth_response(
    user: User, *, access_token: str, refresh_token: str, expires_in: int
) -> AuthTokenResponse:
    return AuthTokenResponse(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone_number=user.phone_number,
        user_type=user.user_type,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


async def _issue_and_send_otp(
    db: AsyncSession,
    queue: ArqRedis,
    *,
    user: User,
    purpose: OtpPurpose,
    locale: str,
) -> None:
    await auth_repo.invalidate_active_otps(db, user_id=user.id, purpose=purpose)
    code = generate_otp_code()
    await auth_repo.create_otp_code(
        db,
        user_id=user.id,
        code_hash=hash_token(code),
        purpose=purpose,
        expire_minutes=settings.otp_expire_minutes,
    )
    await db.commit()
    await queue.enqueue_job(
        TASK_SEND_OTP_EMAIL,
        to=user.email,
        first_name=user.first_name,
        code=code,
        minutes=settings.otp_expire_minutes,
        locale=locale,
        purpose=purpose.value,
    )


async def signup_email(
    db: AsyncSession, queue: ArqRedis, *, data: SignupEmailRequest, locale: str
) -> SignupResponse:
    if await users_repo.get_user_by_email(db, data.email):
        raise EmailAlreadyExistsError()
    if data.phone_number and await users_repo.get_user_by_phone(db, data.phone_number):
        raise PhoneAlreadyExistsError()

    user = await users_repo.create_user(
        db,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone_number=data.phone_number,
        password_hash=hash_password(data.password),
        user_type=UserType(data.user_type),
        is_email_verified=False,
    )
    await users_repo.create_auth_identity(
        db, user_id=user.id, provider=AuthProvider.EMAIL, provider_user_id=str(user.id)
    )

    await _issue_and_send_otp(
        db, queue, user=user, purpose=OtpPurpose.EMAIL_VERIFICATION, locale=locale
    )

    return SignupResponse(message=t("auth.signup_success", locale), email=user.email)


async def verify_email(db: AsyncSession, *, data: VerifyEmailRequest) -> AuthTokenResponse:
    user = await users_repo.get_user_by_email(db, data.email)
    if not user:
        raise InvalidOtpError()

    if not user.is_email_verified:
        otp = await auth_repo.get_latest_active_otp(
            db, user_id=user.id, purpose=OtpPurpose.EMAIL_VERIFICATION
        )
        if not otp:
            raise InvalidOtpError()
        if otp.expires_at < datetime.now(UTC):
            raise OtpExpiredError()
        if otp.attempts >= MAX_OTP_ATTEMPTS:
            raise TooManyOtpAttemptsError()

        if hash_token(data.code) != otp.code_hash:
            otp.attempts += 1
            await db.commit()
            raise InvalidOtpError()

        otp.consumed_at = datetime.now(UTC)
        user.is_email_verified = True

    access_token, refresh_token, expires_in = await _issue_token_pair(db, user)
    await db.commit()
    return _to_auth_response(
        user, access_token=access_token, refresh_token=refresh_token, expires_in=expires_in
    )


async def resend_verification(
    db: AsyncSession,
    queue: ArqRedis,
    redis: Redis,
    *,
    data: ResendVerificationRequest,
    locale: str,
) -> MessageResponse:
    await check_rate_limit(
        redis, key=f"otp_resend:{data.email.lower()}", limit=3, window_seconds=300
    )

    user = await users_repo.get_user_by_email(db, data.email)
    if user and not user.is_email_verified:
        await _issue_and_send_otp(
            db, queue, user=user, purpose=OtpPurpose.EMAIL_VERIFICATION, locale=locale
        )

    return MessageResponse(message=t("auth.verification_resent", locale))


async def login(db: AsyncSession, redis: Redis, *, data: LoginRequest) -> AuthTokenResponse:
    await check_rate_limit(
        redis, key=f"login_attempts:{data.email.lower()}", limit=10, window_seconds=900
    )

    user = await users_repo.get_user_by_email(db, data.email)
    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise InvalidCredentialsError()

    if not user.is_active:
        raise UserNotActiveError()

    if not user.is_email_verified:
        raise EmailNotVerifiedError()

    access_token, refresh_token, expires_in = await _issue_token_pair(
        db, user, remember_me=data.remember_me
    )
    await db.commit()
    return _to_auth_response(
        user, access_token=access_token, refresh_token=refresh_token, expires_in=expires_in
    )


async def social_login(
    db: AsyncSession, *, provider: AuthProvider, data: SocialLoginRequest
) -> AuthTokenResponse:
    profile = await verify_social_token(provider, data.provider_token)

    identity = await users_repo.get_identity(db, provider, profile.provider_user_id)
    if identity:
        user = await users_repo.get_user_by_id(db, identity.user_id)
        if not user:
            raise SocialAuthError()
    else:
        user = await users_repo.get_user_by_email(db, profile.email)
        if user:
            await users_repo.create_auth_identity(
                db, user_id=user.id, provider=provider, provider_user_id=profile.provider_user_id
            )
            if profile.email_verified and not user.is_email_verified:
                user.is_email_verified = True
        else:
            if not data.user_type:
                raise UserTypeRequiredError()
            user = await users_repo.create_user(
                db,
                first_name=profile.first_name,
                last_name=profile.last_name,
                email=profile.email,
                phone_number=None,
                password_hash=None,
                user_type=UserType(data.user_type),
                is_email_verified=profile.email_verified,
            )
            await users_repo.create_auth_identity(
                db,
                user_id=user.id,
                provider=provider,
                provider_user_id=profile.provider_user_id,
            )

    if not user.is_active:
        raise UserNotActiveError()

    access_token, refresh_token, expires_in = await _issue_token_pair(db, user)
    await db.commit()
    return _to_auth_response(
        user, access_token=access_token, refresh_token=refresh_token, expires_in=expires_in
    )


async def refresh_access_token(
    db: AsyncSession, *, data: RefreshTokenRequest
) -> AuthTokenResponse:
    token_hash = hash_token(data.refresh_token)
    stored = await auth_repo.get_refresh_token_by_hash(db, token_hash)
    if not stored or stored.revoked_at is not None or stored.expires_at < datetime.now(UTC):
        raise InvalidRefreshTokenError()

    user = await users_repo.get_user_by_id(db, stored.user_id)
    if not user or not user.is_active:
        raise InvalidRefreshTokenError()

    await auth_repo.revoke_refresh_token(db, stored)
    access_token, new_refresh_token, expires_in = await _issue_token_pair(
        db, user, remember_me=stored.remember_me
    )
    await db.commit()
    return _to_auth_response(
        user, access_token=access_token, refresh_token=new_refresh_token, expires_in=expires_in
    )


async def logout(db: AsyncSession, *, data: LogoutRequest, locale: str) -> MessageResponse:
    token_hash = hash_token(data.refresh_token)
    stored = await auth_repo.get_refresh_token_by_hash(db, token_hash)
    if stored and stored.revoked_at is None:
        await auth_repo.revoke_refresh_token(db, stored)
        await db.commit()
    return MessageResponse(message=t("auth.logged_out", locale))


async def forgot_password(
    db: AsyncSession,
    queue: ArqRedis,
    redis: Redis,
    *,
    data: ForgotPasswordRequest,
    locale: str,
) -> MessageResponse:
    await check_rate_limit(
        redis, key=f"password_reset:{data.email.lower()}", limit=3, window_seconds=900
    )

    user = await users_repo.get_user_by_email(db, data.email)
    if user and user.is_active:
        await _issue_and_send_otp(
            db, queue, user=user, purpose=OtpPurpose.PASSWORD_RESET, locale=locale
        )

    return MessageResponse(message=t("auth.password_reset_requested", locale))


async def reset_password(
    db: AsyncSession, *, data: ResetPasswordRequest, locale: str
) -> MessageResponse:
    user = await users_repo.get_user_by_email(db, data.email)
    if not user:
        raise InvalidOtpError()

    otp = await auth_repo.get_latest_active_otp(
        db, user_id=user.id, purpose=OtpPurpose.PASSWORD_RESET
    )
    if not otp:
        raise InvalidOtpError()
    if otp.expires_at < datetime.now(UTC):
        raise OtpExpiredError()
    if otp.attempts >= MAX_OTP_ATTEMPTS:
        raise TooManyOtpAttemptsError()

    if hash_token(data.code) != otp.code_hash:
        otp.attempts += 1
        await db.commit()
        raise InvalidOtpError()

    otp.consumed_at = datetime.now(UTC)
    user.password_hash = hash_password(data.new_password)
    await auth_repo.revoke_all_refresh_tokens_for_user(db, user_id=user.id)
    await db.commit()

    return MessageResponse(message=t("auth.password_reset_success", locale))
