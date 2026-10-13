"""Security response headers applied to every response.

CSP has no inline scripts (HTMX is loaded as a static file). Inline event
handlers are also forbidden. We allow inline styles because we set tiny
per-element style attributes for layout polish.

The middleware ensures every response has a ``cf_sid`` cookie that
matches the sid used to render CSRF tokens. The sid is set on
``request.state.cf_sid`` BEFORE the route runs, so the CSRF helper
and the response cookie agree.
"""
from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# Strict CSP: no inline scripts, no eval (htmx loaded as static), no frames.
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Pick or create the session id BEFORE the route runs.
        existing = request.cookies.get("cf_sid")
        if existing:
            sid = existing
        else:
            sid = secrets.token_urlsafe(24)
        request.state.cf_sid = sid

        response: Response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", _CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")

        if not request.cookies.get("cf_sid"):
            from app.config import get_settings

            is_prod = get_settings().is_production
            response.set_cookie(
                "cf_sid",
                sid,
                httponly=True,
                samesite="lax",
                secure=is_prod,
                max_age=60 * 60 * 24 * 7,
            )
        return response
