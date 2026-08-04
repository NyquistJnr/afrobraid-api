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


class BraiderNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "BRAIDER_NOT_FOUND"
    message_key = "braider.not_found"


class InvalidSearchLocationError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_SEARCH_LOCATION"
    message_key = "braider.invalid_search_location"


class InvalidSearchDateRangeError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_SEARCH_DATE_RANGE"
    message_key = "braider.invalid_search_date_range"


class InvalidSearchPriceRangeError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_SEARCH_PRICE_RANGE"
    message_key = "braider.invalid_search_price_range"


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


class PhoneVerificationApiUnavailableError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "PHONE_VERIFICATION_API_UNAVAILABLE"
    message_key = "phone_verification.api_unavailable"


class InvalidVerificationCodeError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_VERIFICATION_CODE"
    message_key = "phone_verification.invalid_code"


class StyleCategoryNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "STYLE_CATEGORY_NOT_FOUND"
    message_key = "styles.category_not_found"


class StyleNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "STYLE_NOT_FOUND"
    message_key = "styles.style_not_found"


class StyleNotActiveError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "STYLE_NOT_ACTIVE"
    message_key = "styles.style_not_active"


class StyleVariationNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "STYLE_VARIATION_NOT_FOUND"
    message_key = "styles.variation_not_found"


class AddOnNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "ADDON_NOT_FOUND"
    message_key = "styles.addon_not_found"


class InvalidStyleImageUploadError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_STYLE_IMAGE_UPLOAD"
    message_key = "styles.invalid_image_upload"


class StyleImageNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "STYLE_IMAGE_NOT_FOUND"
    message_key = "styles.image_not_found"


class MaxStyleImagesReachedError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "MAX_STYLE_IMAGES_REACHED"
    message_key = "styles.max_images_reached"


class EntityInUseError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "ENTITY_IN_USE"
    message_key = "styles.entity_in_use"


class BraiderStyleNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "BRAIDER_STYLE_NOT_FOUND"
    message_key = "braider_offerings.style_not_found"


class BraiderStyleAlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "BRAIDER_STYLE_ALREADY_EXISTS"
    message_key = "braider_offerings.style_already_exists"


class BraiderStyleVariationInvalidError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_STYLE_VARIATION"
    message_key = "braider_offerings.invalid_variation"


class BraiderStyleAddonInvalidError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_ADDON"
    message_key = "braider_offerings.invalid_addon"


class AvailabilitySettingsNotConfiguredError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "AVAILABILITY_SETTINGS_NOT_CONFIGURED"
    message_key = "availability.settings_not_configured"


class InvalidTimezoneError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "INVALID_TIMEZONE"
    message_key = "availability.invalid_timezone"


class WeeklyWindowNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "WEEKLY_WINDOW_NOT_FOUND"
    message_key = "availability.window_not_found"


class InvalidAvailabilityWindowTimesError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "INVALID_AVAILABILITY_WINDOW_TIMES"
    message_key = "availability.invalid_window_times"


class OverlappingAvailabilityWindowError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "OVERLAPPING_AVAILABILITY_WINDOW"
    message_key = "availability.overlapping_window"


class AvailabilityExceptionNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "AVAILABILITY_EXCEPTION_NOT_FOUND"
    message_key = "availability.exception_not_found"


class OverlappingAvailabilityExceptionError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "OVERLAPPING_AVAILABILITY_EXCEPTION"
    message_key = "availability.overlapping_exception"


class BraiderStyleDurationMissingError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "BRAIDER_STYLE_DURATION_MISSING"
    message_key = "availability.style_duration_missing"


class StripeApiUnavailableError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "STRIPE_API_UNAVAILABLE"
    message_key = "payment_setup.api_unavailable"


class StripeAccountNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "STRIPE_ACCOUNT_NOT_FOUND"
    message_key = "payment_setup.account_not_found"


class StripeInvalidWebhookSignatureError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "STRIPE_INVALID_WEBHOOK_SIGNATURE"
    message_key = "payment_setup.invalid_webhook_signature"


class BraiderCountryRequiredError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "BRAIDER_COUNTRY_REQUIRED"
    message_key = "payment_setup.country_required"


class InvalidPortfolioImageUploadError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_PORTFOLIO_IMAGE_UPLOAD"
    message_key = "portfolio.invalid_image_upload"


class PortfolioImageNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "PORTFOLIO_IMAGE_NOT_FOUND"
    message_key = "portfolio.image_not_found"


class MaxPortfolioImagesReachedError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "MAX_PORTFOLIO_IMAGES_REACHED"
    message_key = "portfolio.max_images_reached"


class InvalidSettingValueError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_SETTING_VALUE"
    message_key = "platform_settings.invalid_percentage_value"


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMITED"
    message_key = "errors.rate_limited"

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(retry_after_seconds=retry_after_seconds)


class PricingInvariantError(AppError):
    """Raised when the pricing engine's own arithmetic invariants don't hold
    (e.g. line items don't sum to the total) - always a bug, never a user
    input problem, hence 500 rather than 4xx."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "PRICING_INVARIANT_ERROR"
    message_key = "errors.internal_server_error"


class BookingCalculationNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "BOOKING_CALCULATION_NOT_FOUND"
    message_key = "booking_calculation.not_found"


class BookingCalculationExpiredError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "BOOKING_CALCULATION_EXPIRED"
    message_key = "booking_calculation.expired"


class BookingCalculationAlreadyUsedError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "BOOKING_CALCULATION_ALREADY_USED"
    message_key = "booking_calculation.already_used"


class MobileServiceNotOfferedError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "MOBILE_SERVICE_NOT_OFFERED"
    message_key = "booking_calculation.mobile_not_offered"


class ClientLocationMissingError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "CLIENT_LOCATION_MISSING"
    message_key = "booking_calculation.client_location_missing"


class MobileLocationOutOfRangeError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "MOBILE_LOCATION_OUT_OF_RANGE"
    message_key = "booking_calculation.mobile_location_out_of_range"


class BraiderCountryMissingError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "BRAIDER_COUNTRY_MISSING"
    message_key = "booking_calculation.braider_country_missing"


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
            "status": "error",
            "status_label": t("status.error", locale),
            "data": None,
            "error": {
                "code": exc.code,
                "message": t(exc.message_key, locale, **exc.format_kwargs),
            },
        },
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    locale = _locale_of(request)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "status_label": t("status.error", locale),
            "data": None,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": t("errors.validation_error", locale),
                "details": jsonable_encoder(exc.errors()),
            },
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    locale = _locale_of(request)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "status_label": t("status.error", locale),
            "data": None,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": t("errors.internal_server_error", locale),
            },
        },
    )


class InvalidBookingTransitionError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "INVALID_BOOKING_TRANSITION"
    message_key = "booking.invalid_transition"


class BraiderNotPayableError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "BRAIDER_NOT_PAYABLE"
    message_key = "booking.braider_not_payable"


class DoubleBookingError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "DOUBLE_BOOKING"
    message_key = "booking.double_booking"


class BookingNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "BOOKING_NOT_FOUND"
    message_key = "booking.not_found"


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
