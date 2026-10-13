"""Photo serving tests — covers F4.3 (auth, headers, 404)."""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.auth import service as auth_svc
from app.db import session_scope
from app.models.category import Category
from app.models.item import FoundItem
from app.models.photo import Photo
from app.models.place import Place
from app.models.user import AccountStatus, User
from app.photos.processing import synthesise_test_png
from app.photos.service import attach_photos
from app.security import sign_session


def _user(mobile, approved=True, suspended=False):
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
        u.status = AccountStatus.SUSPENDED if suspended else (AccountStatus.APPROVED if approved else AccountStatus.PENDING)
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


def _make_item_with_photo(finder):
    with session_scope() as s:
        c = Category(name="C", sensitive=False, is_active=True)
        p = Place(name="P", is_active=True)
        s.add(c)
        s.add(p)
        s.commit()
        s.refresh(c)
        s.refresh(p)

        from datetime import date

        u = s.get(User, finder.id)
        item = FoundItem(
            finder_id=u.id,
            category_id=c.id,
            place_id=p.id,
            date_found=date.today(),
            description="x",
            handover_note="",
        )
        s.add(item)
        s.commit()
        s.refresh(item)
        attach_photos(s, item=item, uploads=[(synthesise_test_png(32, 32), "a.png")], by=u)
        s.commit()
        return item.id


def test_logged_out_gets_404(client: TestClient):
    r = client.get("/photos/1", follow_redirects=False)
    assert r.status_code == 404


def test_pending_user_gets_404(client: TestClient):
    u = _user("+8801711111111", approved=False)
    client.cookies.set("cf_session", sign_session({"uid": u.id}))
    r = client.get("/photos/1", follow_redirects=False)
    assert r.status_code == 404


def test_suspended_user_gets_404(client: TestClient):
    u = _user("+8801722222222", suspended=True)
    client.cookies.set("cf_session", sign_session({"uid": u.id}))
    r = client.get("/photos/1", follow_redirects=False)
    assert r.status_code == 404


def test_approved_member_gets_photo_with_headers(client: TestClient):
    u = _user("+8801733333333", approved=True)
    item_id = _make_item_with_photo(u)
    with session_scope() as s:
        photo = s.exec(__import__("sqlmodel").select(Photo).where(Photo.item_id == item_id)).one()
        pid = photo.id
    client.cookies.set("cf_session", sign_session({"uid": u.id}))
    r = client.get(f"/photos/{pid}", follow_redirects=False)
    assert r.status_code == 200
    assert r.headers.get("Cache-Control", "").startswith("private")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("Content-Disposition") == "inline"
    assert r.headers.get("content-type", "").startswith("image/")
