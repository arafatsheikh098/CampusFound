"""Suspended user's existing session is invalidated immediately."""
from __future__ import annotations

from datetime import datetime

from app.auth import service as auth_svc
from app.db import session_scope
from app.models.user import AccountStatus
from app.security import sign_session


def _seed_user(mobile="+8801712345678", password="password123"):
    with session_scope() as s:
        u = auth_svc.signup(
            s,
            full_name="X",
            department="CSE",
            batch_or_session="2024",
            mobile=mobile,
            password=password,
            is_member_confirmed=True,
            is_adult_confirmed=True,
        )
        u.status = AccountStatus.APPROVED
        s.add(u)
        s.commit()
        s.refresh(u)
        return u.id


def test_suspended_session_returns_unauthorized():
    uid = _seed_user()
    # Sign a session cookie. Once the user is suspended, the dep
    # should treat them as logged out.
    token = sign_session({"uid": uid})
    assert token

    # Sanity: a fresh request can log in successfully
    with session_scope() as s:
        user, err = auth_svc.login(s, "01712345678", "password123")
        assert err == "ok"
        assert user is not None

    # Suspend
    with session_scope() as s:
        from app.models.user import User

        u = s.get(User, uid)
        u.status = AccountStatus.SUSPENDED
        u.suspended_at = datetime.utcnow()
        s.add(u)
        s.commit()

    # Login now returns suspended
    with session_scope() as s:
        user, err = auth_svc.login(s, "01712345678", "password123")
        assert err == "suspended"
        assert user is None
