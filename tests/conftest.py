"""Pytest configuration.

Each test gets a fresh SQLite database in a temp file, an isolated
``Settings`` cache, and a fresh FastAPI app.
"""
from __future__ import annotations

import sys

import pytest


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    # Each test runs against a unique SQLite file.
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-tests-only-not-for-prod-use")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("TRUSTED_HOSTS", "*")
    # Drop any secret the previous test may have left in env so
    # the Settings instance never accidentally uses it.
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    # Clear the Settings cache for EVERY module named ``app.config``
    # in ``sys.modules`` — both the current canonical one and any
    # leftover copies from previous ``importlib.reload`` calls. This
    # ensures downstream consumers (e.g. ``app.csrf``) that hold a
    # reference to the OLD ``get_settings`` still see a fresh Settings
    # on next call.
    for name, mod in list(sys.modules.items()):
        if (name == "app.config" or name.startswith("app.config.")) and hasattr(
            mod, "_settings_cache"
        ):
            mod._settings_cache = None
    # Also clear via the public ``cache_clear`` shim so a downstream
    # ``get_settings`` call (which may go through any of the cached
    # module instances) rebuilds.
    if "app.config" in sys.modules:
        sys.modules["app.config"].get_settings.cache_clear()

    # Re-build the engine against the new URL using the app helper so the
    # SQLModel metadata is bound to the same engine.
    from app import db as db_mod

    db_mod.reset_engine(f"sqlite:///{db_path}")

    yield


@pytest.fixture
def app():
    from app.main import create_app

    return create_app()


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)
