"""Application configuration via pydantic-settings.

Reads from environment variables and the .env file (development only).
Production refuses to start with the default SECRET_KEY.
"""
from __future__ import annotations

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


# Module-level cache. Tests can call ``get_settings.cache_clear()`` to
# reset; using the module attribute (rather than ``lru_cache``) means the
# cache is reset whenever the module is reloaded via ``importlib.reload``
# — important for test isolation when one test changes the env.
_settings_cache: "Settings | None" = None


def get_settings() -> Settings:
    """Return a process-wide cached Settings instance.

    Tests that change env vars should call ``get_settings.cache_clear()``
    (or ``app.config.get_settings.cache_clear()``) before re-reading.
    """
    global _settings_cache
    if _settings_cache is None:
        s = Settings()
        s.validate_production()
        _settings_cache = s
    return _settings_cache


def _clear_cache() -> None:
    """Test helper: drop the cached Settings instance."""
    global _settings_cache
    _settings_cache = None


# Provide a ``cache_clear`` attribute so existing call sites that use
# ``get_settings.cache_clear()`` keep working.
get_settings.cache_clear = _clear_cache  # type: ignore[attr-defined]
