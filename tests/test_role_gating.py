"""Pending, rejected and suspended users cannot access member routes.

Parametrized over the three blocked statuses. The test exercises a real
endpoint that uses ``require_member`` once M3 lands; in M2 we cover the
dependency directly.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.auth import service as auth_svc
from app.db import session_scope
from app.deps import require_member
from app.models.user import AccountStatus


def _seed(status: AccountStatus, mobile="+8801712345678"):
    with session_scope() as s:
        u = auth_svc.signup(
            s,
            full_name="X",
            department="CSE",
            batch_or_session="2024",
            mobile=mobile,
            password="password123",
            is_member_confirmed=True,
            is_adult_confirmed=True,
        )
        u.status = status
        if status == AccountStatus.SUSPENDED:
            u.suspended_at = datetime.utcnow()
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


@pytest.mark.parametrize(
    "status",
    [AccountStatus.PENDING, AccountStatus.REJECTED, AccountStatus.SUSPENDED],
)
def test_require_member_blocks_non_approved(status):
    user = _seed(status)
    with pytest.raises(Exception) as exc:
        require_member(user=user)
    assert "403" in str(exc.value) or "status" in str(exc.value.detail).lower()


def test_require_member_allows_approved():
    user = _seed(AccountStatus.APPROVED)
    out = require_member(user=user)
    assert out is user
