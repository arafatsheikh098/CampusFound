"""Contact reveal tests — F7: contact only between custodian and the
approved claimant; never for third parties."""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.auth import service as auth_svc
from app.claims import service as claim_svc
from app.db import session_scope
from app.items import service as item_svc
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


def test_contact_revealed_after_approval(client: TestClient):
    finder = _user("+8801711111111")
    claimant = _user("+8801722222222")
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
        u_c = s.get(User, claimant.id)
        from datetime import date
        item = item_svc.create_item(
            s, finder=u_f, category_id=c.id, place_id=p.id,
            date_found=date.today(), description="x",
            handover_note="Library desk 10-13",
            custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        cl = claim_svc.open_claim(s, item_id=item.id, claimant=u_c, answers=["a"])
        claim_svc.decide_claim(s, claim_id=cl.id, by=u_f, approve=True)

    # Finder sees the claimant's mobile + handover note on the item page
    client.cookies.set("cf_session", sign_session({"uid": finder.id}))
    body = client.get(f"/items/{item.id}").text
    assert "+8801722222222" in body
    assert "Library desk 10-13" in body
    assert "Library desk 10-13" in body

    # Claimant sees the finder's mobile + handover note
    client.cookies.set("cf_session", sign_session({"uid": claimant.id}))
    body = client.get(f"/items/{item.id}").text
    assert "+8801711111111" in body

    # Third party does NOT see contact info
    client.cookies.set("cf_session", sign_session({"uid": third.id}))
    body = client.get(f"/items/{item.id}").text
    assert "+8801711111111" not in body
    assert "+8801722222222" not in body
    assert "Library desk 10-13" not in body
