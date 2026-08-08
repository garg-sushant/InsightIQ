"""Application settings, loaded from environment variables only.

No secret is ever hard-coded outside of an obviously-fake development default,
and those defaults are rejected outright when ``ENVIRONMENT=production``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production"]
AIProviderName = Literal["auto", "grok", "mock"]

# Shipped in .env.example so the stack boots with zero configuration. Refusing
# to start with this value in production is the whole point of it being a
# recognisable constant.
INSECURE_DEV_SECRET = "dev-insecure-secret-key-change-me-0000000000000000000000000000"


class Settings(BaseSettings):
    """Runtime configuration for the InsightIQ API."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---------------------------------------------------------------
    app_name: str = "InsightIQ"
    environment: Environment = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_json: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Database ----------------------------------------------------------
    database_url: str = (
        "postgresql+asyncpg://insightiq:insightiq_dev_password@localhost:5432/insightiq"
    )
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # --- Security ----------------------------------------------------------
    secret_key: str = INSECURE_DEV_SECRET
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # --- Uploads -----------------------------------------------------------
    max_upload_mb: int = 25
    max_upload_rows: int = 500_000

    # --- AI ----------------------------------------------------------------
    ai_provider: AIProviderName = "auto"
    grok_api_key: str = ""
    grok_base_url: str = "https://api.x.ai/v1"
    grok_model: str = "grok-4"
    grok_timeout_seconds: float = 60.0
    grok_max_tokens: int = 2000
    ai_cache_ttl_seconds: int = 3600

    # -----------------------------------------------------------------------
    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return upper

    @model_validator(mode="after")
    def _guard_production_secrets(self) -> Settings:
        if self.environment == "production":
            if self.secret_key == INSECURE_DEV_SECRET or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be set to a unique value of at least 32 characters "
                    "when ENVIRONMENT=production. Generate one with: openssl rand -hex 32"
                )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def sync_database_url(self) -> str:
        """Alembic and the seed script use the sync driver."""
        return self.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Call this, never ``Settings()`` directly."""
    return Settings()


settings: Settings = get_settings()


__all__ = ["AIProviderName", "Environment", "Settings", "get_settings", "settings"]
