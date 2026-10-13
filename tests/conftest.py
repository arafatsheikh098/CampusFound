"""Pytest configuration.

Each test gets a fresh SQLite database in a temp file, an isolated
``Settings`` cache, and a fresh FastAPI app.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

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

    # Reset cached singletons
    from app.config import get_settings

    get_settings.cache_clear()

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
