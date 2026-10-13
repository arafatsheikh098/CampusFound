"""Application configuration via pydantic-settings.

Reads from environment variables and the .env file (development only).
Production refuses to start with the default SECRET_KEY.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default values
_DEFAULT_SECRET = "change-me-in-production-please-use-a-long-random-string"


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    env: str = "development"
    secret_key: str = _DEFAULT_SECRET
    database_url: str = "sqlite:///./campusfound.db"
    trusted_hosts: str = "*"

    # Item lifecycle
    days_date_found_max: int = 60
    days_claim_expiry: int = 7
    days_purge_after: int = 90

    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""

    # Demo
    demo_mode: bool = False

    @field_validator("trusted_hosts")
    @classmethod
    def _strip_trusted_hosts(cls, v: str) -> str:
        return v.strip() or "*"

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def is_demo(self) -> bool:
        return bool(self.demo_mode)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_webhook_secret)

    @property
    def trusted_host_list(self) -> List[str]:
        if self.trusted_hosts.strip() in ("", "*"):
            return ["*"]
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]

    def validate_production(self) -> None:
        """Refuse to start production with the default SECRET_KEY."""
        if self.is_production and self.secret_key == _DEFAULT_SECRET:
            raise RuntimeError(
                "SECRET_KEY must be set to a long random string in production. "
                "Refusing to start."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings instance."""
    s = Settings()
    s.validate_production()
    return s
