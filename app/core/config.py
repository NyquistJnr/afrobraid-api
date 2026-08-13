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
        if v.startswith("postgres://"):
            v = "postgresql+asyncpg://" + v[len("postgres://") :]
        elif v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v.replace("sslmode=", "ssl=")

    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    remember_me_access_token_expire_minutes: int = 43200  # 30 days
    refresh_token_expire_days: int = 30
    remember_me_refresh_token_expire_days: int = 90

    otp_expire_minutes: int = 10
    otp_length: int = 6

    admin_invite_expire_hours: int = 72

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
    frontend_url: str = "http://localhost:3000"
    customer_frontend_url: str = ""
    braider_frontend_url: str = ""
    admin_frontend_url: str = ""

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
    stripe_payments_webhook_secret: str = ""
    stripe_api_version: str = "2024-06-20"

    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""
    paypal_api_base_url: str = "https://api-m.sandbox.paypal.com"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_verify_service_sid: str = ""
    twilio_phone_number: str = ""

    phone_verification_bypass_enabled: bool = False
    phone_verification_bypass_code: str = "000000"

    booking_calculation_ttl_hours: int = 2
    booking_full_payment_threshold_hours: int = 24
    booking_full_payment_margin_hours: int = 2
    client_ip_hash_salt: str = ""

    booking_hold_minutes: int = 30
    booking_cancellation_cutoff_hours: int = 24
    booking_balance_charge_grace_minutes: int = 45
    booking_terms_version: str = "1.0"

    hf_api_key: str = ""
    hf_provider: str = "auto"
    hf_model_id: str = "black-forest-labs/FLUX.1-Kontext-dev"
    hf_request_timeout_seconds: int = 120
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
