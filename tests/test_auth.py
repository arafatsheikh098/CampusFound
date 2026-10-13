"""Auth service and route tests."""
from __future__ import annotations

from datetime import datetime, timedelta

from freezegun import freeze_time
from sqlmodel import select

from app.auth import service as auth_svc
from app.db import session_scope
from app.models.login_attempt import LoginAttempt
from app.models.recovery_code import RecoveryCode
from app.models.user import AccountStatus, User


def _make_user(session, mobile="+8801712345678", password="password123", approved=True, name="Test User"):
    user = auth_svc.signup(
        session,
        full_name=name,
        department="CSE",
        batch_or_session="2024",
        mobile=mobile,
        password=password,
        is_member_confirmed=True,
        is_adult_confirmed=True,
    )
    if approved:
        user.status = AccountStatus.APPROVED
        user.approved_at = datetime.utcnow()
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def test_signup_creates_pending_user():
    with session_scope() as s:
        u = _make_user(s, approved=False)
        assert u.status == AccountStatus.PENDING
        assert u.password_hash.startswith("$argon2")


def test_signup_rejects_duplicate_mobile():
    with session_scope() as s:
        _make_user(s, mobile="+8801712345678")
    with session_scope() as s:
        with __import__("pytest").raises(ValueError):
            _make_user(s, mobile="01712345678")


def test_login_returns_user_for_correct_credentials():
    with session_scope() as s:
        _make_user(s, mobile="+8801712345678", password="password123")
    with session_scope() as s:
        user, err = auth_svc.login(s, "01712345678", "password123")
        assert err == "ok"
        assert user is not None
        assert user.mobile == "+8801712345678"


def test_login_unknown_username_returns_invalid():
    with session_scope() as s:
        user, err = auth_svc.login(s, "01700000000", "password123")
    assert user is None
    assert err == "invalid"


def test_login_wrong_password_returns_invalid():
    with session_scope() as s:
        _make_user(s, mobile="+8801712345678", password="password123")
    with session_scope() as s:
        user, err = auth_svc.login(s, "01712345678", "wrong")
    assert user is None
    assert err == "invalid"


def test_login_pending_returns_pending_error():
    with session_scope() as s:
        _make_user(s, mobile="+8801712345678", approved=False)
    with session_scope() as s:
        user, err = auth_svc.login(s, "01712345678", "password123")
    assert user is None
    assert err == "pending"


def test_login_suspended_returns_suspended_error():
    with session_scope() as s:
        u = _make_user(s, mobile="+8801712345678", approved=True)
        u.status = AccountStatus.SUSPENDED
        s.add(u)
        s.commit()
    with session_scope() as s:
        user, err = auth_svc.login(s, "01712345678", "password123")
    assert user is None
    assert err == "suspended"


def test_login_rate_limited_after_5_failures():
    import pytest
    with session_scope() as s:
        _make_user(s, mobile="+8801712345678", password="password123")
    with freeze_time("2026-01-01 10:00:00"):
        with session_scope() as s:
            for _ in range(5):
                auth_svc.login(s, "01712345678", "wrong")
        with session_scope() as s:
            user, err = auth_svc.login(s, "01712345678", "password123")
    # 6th attempt within 15 min is rate limited
    assert user is None
    assert err == "rate_limited"


def test_login_rate_limited_resets_after_window():
    import pytest
    with session_scope() as s:
        _make_user(s, mobile="+8801712345678", password="password123")
    with freeze_time("2026-01-01 10:00:00"):
        with session_scope() as s:
            for _ in range(5):
                auth_svc.login(s, "01712345678", "wrong")
    # 16 minutes later
    with freeze_time("2026-01-01 10:16:00"):
        with session_scope() as s:
            user, err = auth_svc.login(s, "01712345678", "password123")
    assert err == "ok"
    assert user is not None


def test_recovery_codes_generated_and_consumed_once():
    with session_scope() as s:
        u = _make_user(s, mobile="+8801712345678", approved=True)
        codes = auth_svc.generate_recovery_codes(s, u)
        assert len(codes) == 10
        # All codes are stored hashed
        rows = s.exec(select(RecoveryCode).where(RecoveryCode.user_id == u.id)).all()
        assert len(rows) == 10
        # None of the stored hashes equals the plaintext
        for r in rows:
            assert r.code_hash not in codes
        # Consume one
        first = codes[0]
        assert auth_svc.consume_recovery_code(s, u, first) is True
        # The same code cannot be used again
        assert auth_svc.consume_recovery_code(s, u, first) is False


def test_create_moderator_only_via_cli():
    # The form path: cannot set is_moderator=True through the public signup
    with session_scope() as s:
        u = auth_svc.signup(
            s,
            full_name="X",
            department="CSE",
            batch_or_session="2024",
            mobile="+8801712345678",
            password="password123",
            is_member_confirmed=True,
            is_adult_confirmed=True,
        )
    # After signup, is_moderator must be False
    with session_scope() as s:
        u2 = s.get(User, u.id)
        assert u2.is_moderator is False

    # CLI path: create_moderator produces an approved moderator
    with session_scope() as s:
        m = auth_svc.create_moderator(
            s,
            full_name="Mod",
            department="CSE",
            batch_or_session="2024",
            mobile="+8801722222222",
            password="password123",
        )
        assert m.is_moderator is True
        assert m.status == AccountStatus.APPROVED


def test_suspend_user_blocks_login():
    with session_scope() as s:
        u = _make_user(s, mobile="+8801712345678", approved=True)
    with session_scope() as s:
        u2 = s.get(User, u.id)
        u2.status = AccountStatus.SUSPENDED
        s.add(u2)
        s.commit()
    with session_scope() as s:
        user, err = auth_svc.login(s, "01712345678", "password123")
    assert err == "suspended"
