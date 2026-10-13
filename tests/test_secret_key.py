"""Production SECRET_KEY validation."""
from __future__ import annotations

import importlib
import os


def test_production_refuses_default_secret_key(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "change-me-in-production-please-use-a-long-random-string")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test_prod.db")

    from app.config import get_settings

    get_settings.cache_clear()
    importlib.reload(__import__("app.config", fromlist=["Settings"]))

    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    try:
        s.validate_production()
    except RuntimeError as e:
        assert "SECRET_KEY" in str(e)
    else:
        raise AssertionError("expected validate_production to refuse default secret key")


def test_production_accepts_custom_secret_key(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test_prod2.db")
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    s.validate_production()  # must not raise
