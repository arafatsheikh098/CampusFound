"""Request dependencies for current user, role guards, CSRF check."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.csrf import verify_token
from app.db import get_session
from app.models.user import AccountStatus, User
from app.security import unsign_session

SESSION_COOKIE = "cf_session"


def get_current_user_optional(
    request: Request,
    session: Session = Depends(get_session),
) -> Optional[User]:
    """Return the current user if a valid session exists, else None.

    Suspended users are treated as logged out and their session cookie is
    cleared.
    """
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    payload = unsign_session(token)
    if not payload or "uid" not in payload:
        return None
    user = session.get(User, payload["uid"])
    if user is None:
        return None
    if user.status == AccountStatus.SUSPENDED:
        return None
    return user


def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="login required",
        )
    return user


def require_member(user: User = Depends(get_current_user)) -> User:
    """Approved members only. Pending, rejected, suspended are blocked."""
    if user.status != AccountStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"account status {user.status.value} cannot access this page",
        )
    return user


def require_moderator(user: User = Depends(get_current_user)) -> User:
    if not user.is_moderator or user.status != AccountStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="moderator privileges required",
        )
    return user


async def check_csrf(request: Request) -> None:
    """Async CSRF check used by routes after parsing the form."""
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return
    sid = request.cookies.get("cf_sid") or ""
    form = await request.form()
    token = form.get("csrf_token", "")
    if not sid or not verify_token(str(token), sid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="csrf token missing or invalid",
        )


def login_redirect(path: str = "/login") -> RedirectResponse:
    return RedirectResponse(url=path, status_code=302)
