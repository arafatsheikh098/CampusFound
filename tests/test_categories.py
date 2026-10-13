"""Category sensitive flag tests."""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.auth import service as auth_svc
from app.db import session_scope
from app.models.category import Category
from app.models.user import AccountStatus
from app.security import sign_session


def _login_as_moderator(client: TestClient, mobile="+8801712345678"):
    with session_scope() as s:
        u = auth_svc.signup(
            s,
            full_name="Mod",
            department="CSE",
            batch_or_session="2024",
            mobile=mobile,
            password="password123",
            is_member_confirmed=True,
            is_adult_confirmed=True,
        )
        u.status = AccountStatus.APPROVED
        u.is_moderator = True
        s.add(u)
        s.commit()
        s.refresh(u)
        client.cookies.set("cf_session", sign_session({"uid": u.id}))


def test_moderator_creates_sensitive_category(client):
    _login_as_moderator(client)
    r = client.get("/")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    r = client.post(
        "/categories",
        data={"csrf_token": csrf, "name": "ID card", "sensitive": "1"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    with session_scope() as s:
        c = s.exec(__import__("sqlmodel").select(Category).where(Category.name == "ID card")).one()
        assert c.sensitive is True


def test_toggle_sensitive(client):
    _login_as_moderator(client)
    r = client.get("/")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    client.post("/categories", data={"csrf_token": csrf, "name": "Phone"})
    with session_scope() as s:
        c = s.exec(__import__("sqlmodel").select(Category).where(Category.name == "Phone")).one()
        cid = c.id
        assert c.sensitive is False
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/").text).group(1)
    r = client.post(f"/categories/{cid}/toggle-sensitive", data={"csrf_token": csrf})
    with session_scope() as s:
        c = s.get(Category, cid)
        assert c.sensitive is True
