"""Match visibility tests — matches are only shown to the owner of
either side, never to strangers."""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.auth import service as auth_svc
from app.db import session_scope
from app.items import service as item_svc
from app.lost import service as lost_svc
from app.models.category import Category
from app.models.place import Place
from app.models.user import AccountStatus, User
from app.security import sign_session


def _user(mobile):
    with session_scope() as s:
        u = auth_svc.signup(
            s, full_name="X", department="CSE", batch_or_session="2024",
            mobile=mobile, password="password123",
            is_member_confirmed=True, is_adult_confirmed=True,
        )
        u.status = AccountStatus.APPROVED
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


def test_matches_only_visible_to_owner_or_moderator(client: TestClient):
    finder = _user("+8801711111111")
    owner = _user("+8801722222222")
    third = _user("+8801733333333")
    with session_scope() as s:
        c = Category(name="C", sensitive=False, is_active=True)
        p = Place(name="P", is_active=True)
        s.add(c)
        s.add(p)
        s.commit()
        s.refresh(c)
        s.refresh(p)
        u_f = s.get(User, finder.id)
        u_o = s.get(User, owner.id)
        from datetime import date
        item = item_svc.create_item(
            s, finder=u_f, category_id=c.id, place_id=p.id,
            date_found=date.today(), description="silver pen",
            handover_note="", custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        lost_svc.create_lost_report(
            session=s, owner=u_o, category_id=c.id, place_id=p.id,
            date_lost=date.today(), description="silver pen",
        )
        item_id = item.id

    # Finder sees matches
    client.cookies.set("cf_session", sign_session({"uid": finder.id}))
    body = client.get(f"/items/{item_id}").text
    assert "Possible matches" in body or "matches_title" in body

    # Third party does not see matches
    client.cookies.set("cf_session", sign_session({"uid": third.id}))
    body = client.get(f"/items/{item_id}").text
    # The matches section only renders when the user is finder or
    # moderator. Third party -> empty matches list -> no section.
    assert "Possible matches" not in body
