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

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_verify_service_sid: str = ""
    twilio_phone_number: str = ""

    phone_verification_bypass_enabled: bool = False
    phone_verification_bypass_code: str = "000000"

    @property
    def supported_locales_list(self) -> list[str]:
        return [loc.strip() for loc in self.supported_locales.split(",") if loc.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
