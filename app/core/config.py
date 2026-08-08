from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    debug: bool = False

    database_url: str
    db_echo: bool = False
    redis_url: str

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        # Managed Postgres providers (Railway, Heroku, Neon, ...) hand out
        # postgres:// / postgresql:// URLs, but the async engine needs the
        # asyncpg driver named explicitly in the scheme.
        if v.startswith("postgres://"):
            v = "postgresql+asyncpg://" + v[len("postgres://") :]
        elif v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://") :]
        # asyncpg's connect() takes a keyword arg named `ssl`, not `sslmode`
        # (the psycopg/libpq name) — SQLAlchemy forwards query params
        # straight through as kwargs, so `sslmode` raises a TypeError.
        return v.replace("sslmode=", "ssl=")

    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    remember_me_access_token_expire_minutes: int = 43200  # 30 days
    refresh_token_expire_days: int = 30
    remember_me_refresh_token_expire_days: int = 90

    otp_expire_minutes: int = 10
    otp_length: int = 6

    resend_api_key: str
    email_from: str

    supported_locales: str = "en,fr,de"
    default_locale: str = "en"

    google_client_id: str = ""
    facebook_app_id: str = ""
    facebook_app_secret: str = ""
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""

    cors_origins: str = "http://localhost:3000"

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_endpoint_url: str = ""
    r2_public_base_url: str = ""

    deepl_api_key: str = ""
    deepl_api_url: str = "https://api-free.deepl.com/v2/translate"

    veriff_api_key: str = ""
    veriff_secret_key: str = ""
    veriff_api_url: str = "https://stationapi.veriff.com/v1"
    veriff_callback_url: str = ""

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_connect_refresh_url: str = ""
    stripe_connect_return_url: str = ""
    # Separate secret from stripe_webhook_secret above - that one signs
    # Connect account events (account.updated), this one signs platform
    # payment events (payment_intent.*) on the new webhooks/stripe/payments
    # route. Two endpoints, two secrets, per Stripe's own recommendation for
    # apps that receive both event families.
    stripe_payments_webhook_secret: str = ""
    # Pinned explicitly (design correction #8) so Stripe can't reshape
    # webhook/API payloads out from under this app on their own schedule.
    stripe_api_version: str = "2024-06-20"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_verify_service_sid: str = ""
    twilio_phone_number: str = ""

    phone_verification_bypass_enabled: bool = False
    phone_verification_bypass_code: str = "000000"

    # Booking calculator (app.modules.bookings.calculations) - a DRAFT quote
    # is disposable and cleaned up well before it could be mistaken for a
    # real reservation.
    booking_calculation_ttl_hours: int = 2
    # The pricing engine's full-upfront cutoff: an appointment starting at or
    # before this many hours from now is charged 100% upfront rather than a
    # deposit + later balance. See app.modules.bookings.pricing for the
    # margin added on top of this to avoid scheduling a balance charge that
    # would already be almost due.
    booking_full_payment_threshold_hours: int = 24
    booking_full_payment_margin_hours: int = 2
    # Salt mixed into the SHA-256 hash of a booking-calculator caller's IP
    # before it's stored (booking_calculations.client_ip_hash) - an IP is
    # personal data under GDPR, so the raw address is never persisted.
    client_ip_hash_salt: str = ""

    # A booking sits in PENDING_PAYMENT (holding the calendar slot via the
    # exclusion constraint) until its first payment_intent.succeeds. Past
    # this many minutes with no successful payment, expire_booking_holds
    # (Phase 3+) reclaims the slot.
    booking_hold_minutes: int = 30
    # Customer may cancel for a full-refund-free (deposit forfeited) outcome
    # up to this many hours before the appointment.
    booking_cancellation_cutoff_hours: int = 24
    # balance_charge_due_at = cancellation cutoff + this grace period - kept
    # apart from the cutoff itself so the sweeper never fires right as the
    # cancel window closes (design correction #3).
    booking_balance_charge_grace_minutes: int = 45
    booking_terms_version: str = "1.0"

    # Hugging Face (AI hairstyle try-on) - routed through Hugging Face's
    # Inference Providers (huggingface_hub's AsyncInferenceClient), NOT the
    # old standalone "serverless Inference API" (api-inference.huggingface.co
    # was fully decommissioned). hf_provider="auto" lets HF pick whichever
    # partner provider currently serves hf_model_id fastest; pin it to a
    # specific provider name (e.g. "fal-ai", "replicate") for predictable
    # billing/latency instead.
    hf_api_key: str = ""
    hf_provider: str = "auto"
    hf_model_id: str = "black-forest-labs/FLUX.1-Kontext-dev"
    hf_request_timeout_seconds: int = 120
    # Caps how many try-ons a single user can have in flight at once, so a
    # burst of requests can't run up inference costs or flood the queue.
    tryon_max_pending_per_user: int = 3

    @property
    def supported_locales_list(self) -> list[str]:
        return [loc.strip() for loc in self.supported_locales.split(",") if loc.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
