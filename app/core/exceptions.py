import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.i18n import t

logger = logging.getLogger("app")


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "APP_ERROR"
    message_key: str = "errors.generic"

    def __init__(self, **format_kwargs: Any) -> None:
        self.format_kwargs = format_kwargs
        super().__init__(self.code)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    message_key = "errors.not_found"


class InvalidCredentialsError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_CREDENTIALS"
    message_key = "auth.invalid_credentials"


class EmailNotVerifiedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "EMAIL_NOT_VERIFIED"
    message_key = "auth.email_not_verified"


class EmailAlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "EMAIL_ALREADY_EXISTS"
    message_key = "auth.email_already_exists"


class PhoneAlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "PHONE_ALREADY_EXISTS"
    message_key = "auth.phone_already_exists"


class InvalidOtpError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_OTP"
    message_key = "auth.invalid_otp"


class OtpExpiredError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "OTP_EXPIRED"
    message_key = "auth.otp_expired"


class TooManyOtpAttemptsError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "TOO_MANY_OTP_ATTEMPTS"
    message_key = "auth.too_many_otp_attempts"


class InvalidRefreshTokenError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_REFRESH_TOKEN"
    message_key = "auth.invalid_refresh_token"


class InvalidAccessTokenError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_ACCESS_TOKEN"
    message_key = "auth.invalid_access_token"


class UserNotActiveError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "USER_NOT_ACTIVE"
    message_key = "auth.user_not_active"


class ForbiddenRoleError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    message_key = "auth.forbidden"


class AdminSignupBlockedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "ADMIN_SIGNUP_BLOCKED"
    message_key = "auth.admin_signup_blocked"


class SocialAuthError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "SOCIAL_AUTH_FAILED"
    message_key = "auth.social_auth_failed"


class UnsupportedProviderError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "UNSUPPORTED_PROVIDER"
    message_key = "auth.unsupported_provider"


class UserTypeRequiredError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "USER_TYPE_REQUIRED"
    message_key = "auth.user_type_required"


class InvalidLogoUploadError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_LOGO_UPLOAD"
    message_key = "braider.invalid_logo_upload"


class LogoNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "LOGO_NOT_FOUND"
    message_key = "braider.logo_not_found"


class VeriffApiUnavailableError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "VERIFF_API_UNAVAILABLE"
    message_key = "veriff.api_unavailable"


class InvalidWebhookSignatureError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_WEBHOOK_SIGNATURE"
    message_key = "veriff.invalid_webhook_signature"


class VeriffSessionNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "VERIFF_SESSION_NOT_FOUND"
    message_key = "veriff.session_not_found"


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMITED"
    message_key = "errors.rate_limited"

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(retry_after_seconds=retry_after_seconds)


def _locale_of(request: Request) -> str:
    return getattr(request.state, "locale", "en")


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    locale = _locale_of(request)
    headers = {}
    if isinstance(exc, RateLimitedError):
        headers["Retry-After"] = str(exc.retry_after_seconds)
    return JSONResponse(
        status_code=exc.status_code,
        headers=headers,
        content={
            "error": {
                "code": exc.code,
                "message": t(exc.message_key, locale, **exc.format_kwargs),
            }
        },
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    locale = _locale_of(request)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": t("errors.validation_error", locale),
                "details": jsonable_encoder(exc.errors()),
            }
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    locale = _locale_of(request)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": t("errors.internal_server_error", locale),
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
