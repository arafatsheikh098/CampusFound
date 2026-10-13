"""CSRF token helpers.

Tokens are bound to the session cookie; the value is a constant-time
comparison. The real session layer is added in M2 — for M1 this provides
a working CSRF token derived from a signed cookie so the base template
renders correctly.
"""
from __future__ import annotations

import hmac
import secrets
from hashlib import sha256

from fastapi import Request

from app.config import get_settings


def _key() -> bytes:
    return get_settings().secret_key.encode("utf-8")


def issue_token(session_id: str) -> str:
    """Issue a CSRF token bound to ``session_id``."""
    nonce = secrets.token_urlsafe(16)
    mac = hmac.new(_key(), f"{session_id}:{nonce}".encode("utf-8"), sha256).hexdigest()
    return f"{nonce}.{mac}"


def verify_token(token: str, session_id: str) -> bool:
    if not token or "." not in token:
        return False
    nonce, mac = token.split(".", 1)
    expected = hmac.new(_key(), f"{session_id}:{nonce}".encode("utf-8"), sha256).hexdigest()
    return hmac.compare_digest(mac, expected)


def get_or_create_session_id(request: Request) -> str:
    """Return the session id from the cookie, or create one (used by M1
    base template to render CSRF tokens; M2 will sign and persist it).
    """
    sid = request.cookies.get("cf_sid")
    if not sid:
        sid = secrets.token_urlsafe(24)
    return sid


def csrf_token_for(request: Request) -> str:
    """Return a CSRF token for the current request's session id."""
    sid = get_or_create_session_id(request)
    return issue_token(sid)
