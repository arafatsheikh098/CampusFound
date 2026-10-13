"""Security headers are present on every response (F9 / M9)."""
from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def test_security_headers_on_landing(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    # CSP must be set, with no inline scripts.
    csp = r.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
    assert "frame-ancestors 'none'" in csp
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("Referrer-Policy") == "no-referrer"
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_security_headers_on_404(client: TestClient):
    r = client.get("/no-such-page-xyz")
    assert r.status_code == 404
    assert r.headers.get("Content-Security-Policy", "").startswith("default-src")
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_cf_sid_cookie_set_on_first_request(client: TestClient):
    r = client.get("/")
    set_cookie = r.headers.get("set-cookie", "")
    assert "cf_sid" in set_cookie
    assert "httponly" in set_cookie.lower()


def test_htmx_loaded_from_static_no_inline_script(client: TestClient):
    r = client.get("/")
    body = r.text
    # The HTMX script is loaded as an external file.
    assert "/static/htmx/htmx.min.js" in body
    # The only inline script sets allowEval = false. Make sure there are
    # no eval(...) or Function(...) usages anywhere.
    assert "eval(" not in body
    # And CSP forbids inline scripts.
    csp = r.headers.get("Content-Security-Policy", "")
    assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]


def test_cf_sid_cookie_is_secure_in_production(monkeypatch):
    """In production the cf_sid cookie must be Secure (HTTPS-only)."""
    from app import config

    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    config.get_settings.cache_clear()
    # Rebuild the app under production settings.
    if "app.main" in importlib.sys.modules:
        importlib.reload(importlib.import_module("app.main"))
    from app.main import app  # noqa: F401 — ensure import succeeds

    c = TestClient(importlib.import_module("app.main").app)
    r = c.get("/")
    set_cookie = r.headers.get("set-cookie", "")
    assert "cf_sid" in set_cookie
    assert "secure" in set_cookie.lower(), "production must set Secure on cf_sid"
    # Restore dev settings for the rest of the suite.
    monkeypatch.setenv("ENV", "development")
    config.get_settings.cache_clear()
