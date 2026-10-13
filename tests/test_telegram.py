"""Telegram webhook: secret check, /start <code> binds chat, unknown is no-op."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import service as auth_svc
from app.db import session_scope
from app.models.user import AccountStatus, User


def _user_with_code(mobile="+8801711111111", code="ABC123XYZ"):
    with session_scope() as s:
        u = auth_svc.signup(
            s, full_name="X", department="CSE", batch_or_session="2024",
            mobile=mobile, password="password123",
            is_member_confirmed=True, is_adult_confirmed=True,
        )
        u.status = AccountStatus.APPROVED
        u.telegram_link_code = code
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


def test_webhook_rejects_wrong_secret(client: TestClient):
    r = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "WRONG"},
        json={"message": {"chat": {"id": 1}, "text": "/start X"}},
    )
    assert r.status_code == 403


def test_webhook_with_no_secret_rejected(client: TestClient):
    """The middleware accepts only requests with the configured secret.

    Tests run with the default empty TELEGRAM_WEBHOOK_SECRET, so the
    handler treats any incoming secret as wrong.
    """
    r = client.post(
        "/telegram/webhook",
        json={"message": {"chat": {"id": 1}, "text": "/start X"}},
    )
    assert r.status_code == 403


def test_webhook_with_correct_secret_binds_chat(client: TestClient, monkeypatch):
    # Set the secret
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret-xyz")
    from app.config import get_settings
    get_settings.cache_clear()
    s_now = get_settings()
    print("DEBUG settings secret:", repr(s_now.telegram_webhook_secret))
    u = _user_with_code(code="MYCODE99")
    # Force the app to re-read settings — easiest: rebuild it.
    from app.main import create_app
    new_app = create_app()
    from fastapi.testclient import TestClient
    c2 = TestClient(new_app)
    r = c2.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-xyz"},
        json={"message": {"chat": {"id": 99999}, "text": "/start MYCODE99"}},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    with session_scope() as s:
        u2 = s.get(User, u.id)
        assert u2.telegram_chat_id == 99999
        assert u2.telegram_link_code is None


def test_webhook_unknown_code_no_op(client: TestClient, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "s2")
    from app.config import get_settings
    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import create_app
    c2 = TestClient(create_app())
    r = c2.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "s2"},
        json={"message": {"chat": {"id": 12345}, "text": "/start NOPECODE"}},
    )
    assert r.status_code == 200
    # No user was bound
    with session_scope() as s:
        u = s.exec(
            __import__("sqlmodel").select(User).where(
                User.telegram_chat_id == 12345
            )
        ).one_or_none()
        assert u is None


def test_webhook_non_start_text_is_noop(client: TestClient, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "s3")
    from app.config import get_settings
    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import create_app
    c2 = TestClient(create_app())
    r = c2.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "s3"},
        json={"message": {"chat": {"id": 55555}, "text": "hi there"}},
    )
    assert r.status_code == 200
