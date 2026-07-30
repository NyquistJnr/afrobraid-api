from typing import Literal

from arq import ArqRedis
from fastapi import APIRouter, Depends, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.queue import get_task_queue
from app.core.rate_limit import ip_rate_limiter
from app.core.redis import get_redis
from app.modules.auth import service
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
from app.modules.users.models import AuthProvider

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

SocialProviderPath = Literal["google", "facebook", "tiktok"]
_PROVIDER_MAP = {
    "google": AuthProvider.GOOGLE,
    "facebook": AuthProvider.FACEBOOK,
    "tiktok": AuthProvider.TIKTOK,
}


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.post(
    "/signup/email",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(ip_rate_limiter(key_prefix="signup", limit=5, window_seconds=3600))],
)
async def signup_email(
    payload: SignupEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> SignupResponse:
    return await service.signup_email(db, queue, data=payload, locale=_locale(request))


@router.post(
    "/verify-email",
    response_model=AuthTokenResponse,
    dependencies=[Depends(ip_rate_limiter(key_prefix="verify-email", limit=10, window_seconds=3600))],
)
async def verify_email(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    return await service.verify_email(db, data=payload)


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    dependencies=[
        Depends(ip_rate_limiter(key_prefix="resend-verification", limit=5, window_seconds=3600))
    ],
)
async def resend_verification(
    payload: ResendVerificationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    return await service.resend_verification(
        db, queue, redis, data=payload, locale=_locale(request)
    )


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    dependencies=[Depends(ip_rate_limiter(key_prefix="login", limit=20, window_seconds=900))],
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AuthTokenResponse:
    return await service.login(db, redis, data=payload)


@router.post(
    "/social/{provider}",
    response_model=AuthTokenResponse,
    dependencies=[Depends(ip_rate_limiter(key_prefix="social-login", limit=20, window_seconds=3600))],
)
async def social_login(
    provider: SocialProviderPath,
    payload: SocialLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    return await service.social_login(db, provider=_PROVIDER_MAP[provider], data=payload)


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh_access_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    return await service.refresh_access_token(db, data=payload)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    payload: LogoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    return await service.logout(db, data=payload, locale=_locale(request))


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    dependencies=[
        Depends(ip_rate_limiter(key_prefix="forgot-password", limit=5, window_seconds=3600))
    ],
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    return await service.forgot_password(db, queue, redis, data=payload, locale=_locale(request))


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    dependencies=[
        Depends(ip_rate_limiter(key_prefix="reset-password", limit=10, window_seconds=3600))
    ],
)
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    return await service.reset_password(db, data=payload, locale=_locale(request))
