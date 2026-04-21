from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Trading Platform"
    debug: bool = False

    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/app_db",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    celery_broker_url: str = Field(default="redis://localhost:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND")

    jwt_secret: str = Field(default="change-me", alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    encryption_key: str = Field(default="", alias="ENCRYPTION_KEY")

    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(default="http://localhost:8000/auth/google/callback", alias="GOOGLE_REDIRECT_URI")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_login_bot_token: str = Field(default="", alias="TELEGRAM_LOGIN_BOT_TOKEN")

    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="noreply@localhost", alias="SMTP_FROM")

    binance_testnet: bool = Field(default=True, alias="BINANCE_TESTNET")

    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    http_rate_limit: str = Field(default="100/minute", alias="HTTP_RATE_LIMIT")

    max_api_keys_user: int = Field(default=5, alias="MAX_API_KEYS_USER")
    max_api_keys_vip: int = Field(default=20, alias="MAX_API_KEYS_VIP")
    max_api_keys_support: int = Field(default=10, alias="MAX_API_KEYS_SUPPORT")
    max_api_keys_admin: int = Field(default=100, alias="MAX_API_KEYS_ADMIN")
    max_api_keys_superadmin: int = Field(default=1000, alias="MAX_API_KEYS_SUPERADMIN")

    max_active_bots_user: int = Field(default=3, alias="MAX_ACTIVE_BOTS_USER")
    max_active_bots_vip: int = Field(default=10, alias="MAX_ACTIVE_BOTS_VIP")
    max_active_bots_support: int = Field(default=5, alias="MAX_ACTIVE_BOTS_SUPPORT")
    max_active_bots_admin: int = Field(default=50, alias="MAX_ACTIVE_BOTS_ADMIN")
    max_active_bots_superadmin: int = Field(default=500, alias="MAX_ACTIVE_BOTS_SUPERADMIN")

    exchange_rate_per_minute: int = Field(default=1200, alias="EXCHANGE_RATE_PER_MINUTE")
    exchange_rate_burst: int = Field(default=50, alias="EXCHANGE_RATE_BURST")

    frontend_base_url: str = Field(default="http://localhost:3000", alias="FRONTEND_BASE_URL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
