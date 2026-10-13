"""Places tests."""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.db import session_scope
from app.models.place import Place
from app.models.user import AccountStatus, User
from app.security import sign_session


def _login_as_moderator(client: TestClient, mobile="+8801712345678"):
    with session_scope() as s:
        from app.auth import service as auth_svc

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
        return u


def _login_as_member(client: TestClient, mobile="+8801722222222"):
    with session_scope() as s:
        from app.auth import service as auth_svc

        u = auth_svc.signup(
            s,
            full_name="Mem",
            department="CSE",
            batch_or_session="2024",
            mobile=mobile,
            password="password123",
            is_member_confirmed=True,
            is_adult_confirmed=True,
        )
        u.status = AccountStatus.APPROVED
        s.add(u)
        s.commit()
        s.refresh(u)
        client.cookies.set("cf_session", sign_session({"uid": u.id}))
        return u


def test_moderator_can_add_place(client):
    _login_as_moderator(client)
    r = client.get("/")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    r = client.post(
        "/places",
        data={"csrf_token": csrf, "name": "Library"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    with session_scope() as s:
        ps = s.exec(__import__("sqlmodel").select(Place)).all()
        assert any(p.name == "Library" for p in ps)


def test_non_moderator_cannot_add_place(client):
    _login_as_member(client)
    r = client.get("/")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    r = client.post(
        "/places",
        data={"csrf_token": csrf, "name": "Should not work"},
        follow_redirects=False,
    )
    assert r.status_code == 403
    with session_scope() as s:
        ps = s.exec(__import__("sqlmodel").select(Place)).all()
        assert all(p.name != "Should not work" for p in ps)


def test_duplicate_place_rejected(client):
    _login_as_moderator(client)
    r = client.get("/")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    client.post("/places", data={"csrf_token": csrf, "name": "Library"})
    csrf2 = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/").text).group(1)
    r = client.post(
        "/places", data={"csrf_token": csrf2, "name": "Library"}, follow_redirects=False
    )
    assert r.status_code == 400
