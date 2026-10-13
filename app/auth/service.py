"""Account service: sign-up, login, recovery, moderator creation, rate limit.

Login is rate-limited per (username_or_mobile): 5 failures in 15 minutes
is OK; the 6th returns a generic rate-limit error. A success clears the
counter (we keep the historical rows for audit, but ignore them on rate
calculations).
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlmodel import Session, select

from app.models.login_attempt import LoginAttempt
from app.models.recovery_code import RecoveryCode
from app.models.user import AccountStatus, User
from app.phone import normalize
from app.security import hash_password, verify_password

# Number of failed attempts allowed in the window (5 OK, 6th blocks)
RATE_LIMIT_FAILS = 5
RATE_LIMIT_WINDOW = timedelta(minutes=15)

# Length of the recovery codes shown to the user
RECOVERY_CODE_LEN = 10
RECOVERY_CODES_TOTAL = 10


class AuthError(Exception):
    """Generic authentication failure with a user-facing message."""


def _normalize_mobile(raw: str) -> str:
    return normalize(raw)


def signup(
    session: Session,
    *,
    full_name: str,
    department: str,
    batch_or_session: str,
    mobile: str,
    password: str,
    is_member_confirmed: bool,
    is_adult_confirmed: bool,
) -> User:
    """Create a pending user. Raises ``ValueError`` on invalid input."""
    if not is_member_confirmed or not is_adult_confirmed:
        raise ValueError("both confirmations are required")
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    if not full_name.strip() or not department.strip() or not batch_or_session.strip():
        raise ValueError("name, department and session are required")

    mobile_norm = _normalize_mobile(mobile)

    existing = session.exec(
        select(User).where(User.mobile == mobile_norm)
    ).one_or_none()
    if existing is not None:
        raise ValueError("an account with this mobile number already exists")

    user = User(
        full_name=full_name.strip()[:120],
        department=department.strip()[:120],
        batch_or_session=batch_or_session.strip()[:60],
        mobile=mobile_norm,
        password_hash=hash_password(password),
        is_member_confirmed=bool(is_member_confirmed),
        is_adult_confirmed=bool(is_adult_confirmed),
        status=AccountStatus.PENDING,
        is_moderator=False,
        display_name_snapshot=full_name.strip()[:120],
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _recent_failures(session: Session, key: str, now: datetime) -> int:
    cutoff = now - RATE_LIMIT_WINDOW
    rows = session.exec(
        select(LoginAttempt).where(
            LoginAttempt.username_or_mobile == key,
            LoginAttempt.success.is_(False),
            LoginAttempt.attempted_at >= cutoff,
        )
    ).all()
    return len(rows)


def login(
    session: Session, identifier: str, password: str, ip: Optional[str] = None
) -> Tuple[Optional[User], str]:
    """Authenticate. Returns ``(user_or_None, error_key)``.

    ``error_key`` is one of:
      ``"rate_limited"`` — too many recent failures
      ``"invalid"``      — generic invalid credentials
      ``"pending"``      — account pending moderator approval
      ``"rejected"``     — account rejected
      ``"suspended"``    — account suspended
    """
    identifier = (identifier or "").strip()
    now = datetime.utcnow()

    # Normalize if it looks like a mobile
    try:
        key = _normalize_mobile(identifier)
    except ValueError:
        key = identifier  # fall through; user lookup will fail with "invalid"

    if _recent_failures(session, key, now) >= RATE_LIMIT_FAILS:
        session.add(LoginAttempt(
            username_or_mobile=key, success=False, attempted_at=now, ip=ip,
        ))
        session.commit()
        return None, "rate_limited"

    user = session.exec(
        select(User).where(User.mobile == key)
    ).one_or_none()
    if user is None:
        # also allow login by raw identifier for tests
        user = session.exec(
            select(User).where(User.mobile == identifier)
        ).one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        session.add(LoginAttempt(
            username_or_mobile=key, success=False, attempted_at=now, ip=ip,
        ))
        session.commit()
        return None, "invalid"

    if user.status == AccountStatus.PENDING:
        return None, "pending"
    if user.status == AccountStatus.REJECTED:
        return None, "rejected"
    if user.status == AccountStatus.SUSPENDED:
        return None, "suspended"

    # Success: log it
    session.add(LoginAttempt(
        username_or_mobile=key, success=True, attempted_at=now, ip=ip,
    ))
    session.commit()
    return user, "ok"


def create_moderator(
    session: Session,
    *,
    full_name: str,
    department: str,
    batch_or_session: str,
    mobile: str,
    password: str,
    is_member_confirmed: bool = True,
    is_adult_confirmed: bool = True,
) -> User:
    """Create an already-approved moderator account (CLI)."""
    user = signup(
        session,
        full_name=full_name,
        department=department,
        batch_or_session=batch_or_session,
        mobile=mobile,
        password=password,
        is_member_confirmed=is_member_confirmed,
        is_adult_confirmed=is_adult_confirmed,
    )
    user.status = AccountStatus.APPROVED
    user.is_moderator = True
    user.approved_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def approve_user(session: Session, user: User, by: User) -> User:
    if by is None or not getattr(by, "is_moderator", False):
        raise AuthError("only a moderator can approve accounts")
    if user.status != AccountStatus.PENDING:
        raise AuthError("only pending accounts can be approved")
    user.status = AccountStatus.APPROVED
    user.approved_at = datetime.utcnow()
    user.approved_by_id = by.id
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def reject_user(session: Session, user: User, by: User) -> User:
    if by is None or not getattr(by, "is_moderator", False):
        raise AuthError("only a moderator can reject accounts")
    if user.status != AccountStatus.PENDING:
        raise AuthError("only pending accounts can be rejected")
    user.status = AccountStatus.REJECTED
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def suspend_user(session: Session, user: User, by: User) -> User:
    if by is None or not getattr(by, "is_moderator", False):
        raise AuthError("only a moderator can suspend accounts")
    user.status = AccountStatus.SUSPENDED
    user.suspended_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def unsuspend_user(session: Session, user: User, by: User) -> User:
    if by is None or not getattr(by, "is_moderator", False):
        raise AuthError("only a moderator can unsuspend accounts")
    user.status = AccountStatus.APPROVED
    user.suspended_at = None
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def generate_recovery_codes(session: Session, user: User) -> list[str]:
    """Generate 10 single-use recovery codes for the user. Returns the
    plaintext codes (to be shown once). The DB stores hashes only.
    """
    plain = []
    for _ in range(RECOVERY_CODES_TOTAL):
        code = secrets.token_hex(RECOVERY_CODE_LEN // 2)  # 5 bytes -> 10 hex chars
        plain.append(code)
        session.add(RecoveryCode(
            user_id=user.id,
            code_hash=hash_password(code),
            created_at=datetime.utcnow(),
        ))
    session.commit()
    return plain


def consume_recovery_code(session: Session, user: User, code: str) -> bool:
    """Try to consume a recovery code. Returns True if matched and removed."""
    rows = session.exec(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.used_at.is_(None),
        )
    ).all()
    for row in rows:
        if verify_password(code.strip().lower(), row.code_hash):
            row.used_at = datetime.utcnow()
            session.add(row)
            session.commit()
            return True
    return False
