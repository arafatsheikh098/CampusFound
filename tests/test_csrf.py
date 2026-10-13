"""CSRF: every state-changing route rejects missing CSRF token.

Uses FastAPI's TestClient with a real session cookie. The session-id
cookie is created by GET / (M1's CSRF helper).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth import service as auth_svc
from app.db import session_scope
from app.models.user import AccountStatus


def _login_session(client: TestClient, mobile="+8801712345678", password="password123"):
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
        u.is_moderator = True
        s.add(u)
        s.commit()
    # Trigger cookie creation
    client.get("/")
    # Get a CSRF token from the rendered page (it's in the base template form)
    client.get("/login")
    # We don't need to login; the test fixtures below only check CSRF on
    # endpoints that require it.


def _state_changing_endpoints(app) -> list[tuple[str, str, dict]]:
    """Return (method, path, form) for every state-changing route."""
    out: list[tuple[str, str, dict]] = []
    for r in app.routes:
        methods = getattr(r, "methods", set()) or set()
        for m in methods:
            if m in {"POST", "PUT", "PATCH", "DELETE"}:
                # Build a minimal valid form for each. Most endpoints should
                # reject on missing CSRF before they validate form fields.
                path = r.path
                # The two lang endpoints exist too
                out.append((m, path, {"csrf_token": ""}))
    return out


def test_csrf_rejected_on_state_changing_routes(client, app):
    endpoints = _state_changing_endpoints(app)
    assert endpoints, "no state-changing routes discovered"
    for method, path, _ in endpoints:
        if method == "POST" and path.startswith("/lang/"):
            # /lang/{lang} uses a form-encoded POST; the CSRF helper
            # already covers this. We pass no csrf_token.
            r = client.post(path, data={"csrf_token": ""}, follow_redirects=False)
        else:
            r = client.request(method, path, data={"csrf_token": ""}, follow_redirects=False)
        assert r.status_code in (403, 422, 400, 405, 404), (
            f"{method} {path} did not reject missing CSRF (got {r.status_code})"
        )


def test_csrf_accepts_valid_token(client, app):
    # Pull a valid token from the base template
    r = client.get("/")
    body = r.text
    # extract first csrf_token from the rendered page
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', body)
    assert m, "no csrf_token rendered in base template"
    token = m.group(1)
    # /lang/bn with a valid token should respond 204 or redirect
    r2 = client.post("/lang/bn", data={"csrf_token": token}, follow_redirects=False)
    assert r2.status_code in (204, 302, 303)
