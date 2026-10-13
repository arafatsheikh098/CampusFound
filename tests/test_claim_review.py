"""Claim review tests — F6.2: side-by-side answers visible to custodian,
private answers invisible to claimant."""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.auth import service as auth_svc
from app.claims import service as claim_svc
from app.db import session_scope
from app.items import service as item_svc
from app.models.category import Category
from app.models.item import FoundItem
from app.models.place import Place
from app.models.user import AccountStatus, User
from app.security import sign_session


def _user(mobile, approved=True):
    with session_scope() as s:
        u = auth_svc.signup(
            s, full_name="X", department="CSE", batch_or_session="2024",
            mobile=mobile, password="password123",
            is_member_confirmed=True, is_adult_confirmed=True,
        )
        u.status = AccountStatus.APPROVED if approved else AccountStatus.PENDING
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


def _setup():
    finder = _user("+8801711111111")
    claimant = _user("+8801722222222")
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
        item = item_svc.create_item(
            s, finder=u_f, category_id=c.id, place_id=p.id,
            date_found=__import__("datetime").date.today(),
            description="x", handover_note="",
            custody_requested="finder",
            questions=["pet name?"], answers=["SECRET-private-99"],
        )
        claim = claim_svc.open_claim(s, item_id=item.id, claimant=u_c, answers=["my answer"])
        return finder, claimant, item.id, claim.id


def test_custodian_sees_both_answers(client: TestClient):
    finder, claimant, item_id, claim_id = _setup()
    client.cookies.set("cf_session", sign_session({"uid": finder.id}))
    r = client.get(f"/claims/{claim_id}/review")
    body = r.text
    assert r.status_code == 200
    assert "SECRET-private-99" in body
    assert "my answer" in body


def test_claimant_does_not_see_private_answer(client: TestClient):
    finder, claimant, item_id, claim_id = _setup()
    client.cookies.set("cf_session", sign_session({"uid": claimant.id}))
    r = client.get(f"/claims/{claim_id}")
    body = r.text
    assert r.status_code == 200
    assert "SECRET-private-99" not in body
    # Their own answer is shown back to them.
    assert "my answer" in body


def test_third_party_cannot_review(client: TestClient):
    finder, claimant, item_id, claim_id = _setup()
    third = _user("+8801733333333")
    client.cookies.set("cf_session", sign_session({"uid": third.id}))
    r = client.get(f"/claims/{claim_id}/review")
    assert r.status_code == 403
