"""HTML/script in user fields is escaped on render (Jinja autoescape)."""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.auth import service as auth_svc
from app.db import session_scope
from app.items import service as item_svc
from app.models.category import Category
from app.models.place import Place
from app.models.user import AccountStatus, User
from app.security import sign_session


def _seed():
    with session_scope() as s:
        u = auth_svc.signup(
            s,
            full_name="X",
            department="CSE",
            batch_or_session="2024",
            mobile="+8801712345678",
            password="password123",
            is_member_confirmed=True,
            is_adult_confirmed=True,
        )
        u.status = AccountStatus.APPROVED
        s.add(u)
        s.commit()
        s.refresh(u)
        s.add(Place(name="Library", is_active=True))
        s.add(Category(name="Other", is_active=True))
        s.commit()
        return u.id


def test_html_escaped_in_view(client):
    uid = _seed()
    with session_scope() as s:
        user = s.get(User, uid)
        place = s.exec(__import__("sqlmodel").select(Place)).one()
        cat = s.exec(__import__("sqlmodel").select(Category)).one()
        item = item_svc.create_item(
            s,
            finder=user,
            category_id=cat.id,
            place_id=place.id,
            date_found=date.today(),
            description="<script>alert(1)</script> water bottle",
            handover_note="<b>bold</b>",
            custody_requested="finder",
            questions=["q"],
            answers=["a"],
        )
    # Login as the owner
    client.cookies.set("cf_session", sign_session({"uid": uid}))
    r = client.get(f"/items/{item.id}")
    assert r.status_code == 200
    body = r.text
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "<b>bold</b>" not in body
    assert "&lt;b&gt;bold&lt;/b&gt;" in body
