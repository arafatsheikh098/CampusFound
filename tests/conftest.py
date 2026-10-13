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

    # Re-build the engine against the new URL
    from sqlmodel import SQLModel, create_engine

    from app import db as db_mod
    from app.csrf import _key

    db_mod.engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    db_mod.init_db()

    yield


@pytest.fixture
def app():
    from app.main import create_app

    return create_app()


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)
