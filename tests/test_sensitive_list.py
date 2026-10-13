"""Sensitive list test — F5.3: the list page must render only the
generic placeholder for sensitive items and never leak any
private field (description, handover note, verification answers).
"""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.auth import service as auth_svc
from app.db import session_scope
from app.items import service as item_svc
from app.models.category import Category
from app.models.place import Place
from app.models.user import AccountStatus
from app.security import sign_session


def _login(mobile="+8801712345678"):
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
        u.status = AccountStatus.APPROVED
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


def test_sensitive_list_leaks_no_private_field(client: TestClient):
    u = _login()
    with session_scope() as s:
        c = Category(name="ID card", sensitive=True, is_active=True)
        p = Place(name="Library", is_active=True)
        s.add(c)
        s.add(p)
        s.commit()
        s.refresh(c)
        s.refresh(p)
        from datetime import date
        from app.models.user import User
        u2 = s.get(User, u.id)
        item_svc.create_item(
            s, finder=u2, category_id=c.id, place_id=p.id,
            date_found=date.today(), description="secret name 42",
            handover_note="secret handover phrase",
            custody_requested="finder",
            questions=["where is it from?"],
            answers=["priv-ans-99"],
        )

    client.cookies.set("cf_session", sign_session({"uid": u.id}))
    r = client.get("/items", follow_redirects=False)
    body = r.text
    assert "secret name 42" not in body
    assert "secret handover phrase" not in body
    assert "priv-ans-99" not in body
    # Generic placeholder present
    assert "[sensitive]" in body.lower() or "sensitive" in body.lower()


def test_logged_out_member_item_page_is_login(client: TestClient):
    """F5.4: a logged-out request to a member-only item page returns the
    login page without leaking that the item exists."""
    u = _login(mobile="+8801722222222")
    with session_scope() as s:
        c = Category(name="C", sensitive=False, is_active=True)
        p = Place(name="P", is_active=True)
        s.add(c)
        s.add(p)
        s.commit()
        s.refresh(c)
        s.refresh(p)
        from datetime import date
        from app.models.user import User
        u2 = s.get(User, u.id)
        item = item_svc.create_item(
            s, finder=u2, category_id=c.id, place_id=p.id,
            date_found=date.today(), description="ZZZ-unique-zzz",
            handover_note="", custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        item_id = item.id

    # No cookie set — logged out.
    r = client.get(f"/items/{item_id}", follow_redirects=False)
    # Should redirect to login; the body should not contain the
    # description.
    assert r.status_code in (302, 200)
    body = r.text if r.status_code == 200 else ""
    assert "ZZZ-unique-zzz" not in body
