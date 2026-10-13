"""Deployment-readiness checks.

These tests do not run the app under a real proxy; they verify the
wiring (middleware, settings, docker files) is in place.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_app_loads_with_trusted_hosts():
    from app.config import get_settings
    from app.main import create_app

    app = create_app()
    # At least one middleware registered: SecurityHeadersMiddleware.
    mw_classes = [m.cls.__name__ for m in app.user_middleware]
    assert "SecurityHeadersMiddleware" in mw_classes


def test_health_endpoint_returns_ok():
    from app.main import create_app

    app = create_app()
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_settings_rejects_default_secret_in_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "change-me-in-production-please-use-a-long-random-string")
    from app.config import Settings, get_settings
    get_settings.cache_clear()
    s = Settings()
    with pytest.raises(RuntimeError):
        s.validate_production()


def test_dockerfile_and_compose_exist():
    root = Path(__file__).resolve().parent.parent
    assert (root / "Dockerfile").exists()
    assert (root / "docker-compose.yml").exists()
    assert (root / ".github" / "workflows" / "ci.yml").exists()


def test_env_example_lists_all_required_vars():
    root = Path(__file__).resolve().parent.parent
    text = (root / ".env.example").read_text()
    for key in (
        "SECRET_KEY",
        "DATABASE_URL",
        "ENV",
        "DAYS_DATE_FOUND_MAX",
        "DAYS_PURGE_AFTER",
        "TELEGRAM_BOT_TOKEN",
        "DEMO_MODE",
    ):
        assert key in text, f"missing {key} in .env.example"
