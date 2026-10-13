"""Claim limit and basic lifecycle tests — covers F6.1."""
from __future__ import annotations

from datetime import date

import pytest

from app.auth import service as auth_svc
from app.claims import service as claim_svc
from app.db import session_scope
from app.items import service as item_svc
from app.models.category import Category
from app.models.claim import Claim, ClaimStatus
from app.models.item import FoundItem
from app.models.place import Place
from app.models.user import AccountStatus, User


def _make_user(mobile):
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


def _make_item(finder):
    with session_scope() as s:
        c = Category(name="C", sensitive=False, is_active=True)
        p = Place(name="P", is_active=True)
        s.add(c)
        s.add(p)
        s.commit()
        s.refresh(c)
        s.refresh(p)
        u = s.get(User, finder.id)
        item = item_svc.create_item(
            s, finder=u, category_id=c.id, place_id=p.id,
            date_found=date.today(), description="x",
            handover_note="", custody_requested="finder",
            questions=["q1", "q2"], answers=["a1", "a2"],
        )
        return item.id


def test_three_attempts_per_member_per_item():
    finder = _make_user("+8801711111111")
    claimant = _make_user("+8801722222222")
    item_id = _make_item(finder)
    with session_scope() as s:
        u_c = s.get(User, claimant.id)
        for i in range(claim_svc.ATTEMPTS_PER_ITEM):
            claim_svc.open_claim(
                s, item_id=item_id, claimant=u_c, answers=["a1", "a2"],
            )
        with pytest.raises(claim_svc.ClaimError):
            claim_svc.open_claim(
                s, item_id=item_id, claimant=u_c, answers=["a1", "a2"],
            )


def test_five_open_claims_per_member():
    finder = _make_user("+8801733333333")
    claimant = _make_user("+8801744444444")
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
        item_ids = []
        for i in range(claim_svc.OPEN_CLAIMS_PER_MEMBER + 1):
            it = item_svc.create_item(
                s, finder=u_f, category_id=c.id, place_id=p.id,
                date_found=date.today(), description="x",
                handover_note="", custody_requested="finder",
                questions=["q"], answers=["a"],
            )
            item_ids.append(it.id)
        for iid in item_ids[: claim_svc.OPEN_CLAIMS_PER_MEMBER]:
            claim_svc.open_claim(s, item_id=iid, claimant=u_c, answers=["a"])
        with pytest.raises(claim_svc.ClaimError):
            claim_svc.open_claim(
                s, item_id=item_ids[-1], claimant=u_c, answers=["a"]
            )


def test_no_self_claim():
    u = _make_user("+8801755555555")
    item_id = _make_item(u)
    with session_scope() as s:
        u2 = s.get(User, u.id)
        with pytest.raises(claim_svc.ClaimError):
            claim_svc.open_claim(
                s, item_id=item_id, claimant=u2, answers=["a1", "a2"],
            )


def test_only_one_approved_claim_per_item():
    finder = _make_user("+8801766666666")
    c1 = _make_user("+8801777777771")
    c2 = _make_user("+8801777777772")
    item_id = _make_item(finder)
    with session_scope() as s:
        u_f = s.get(User, finder.id)
        u_c1 = s.get(User, c1.id)
        u_c2 = s.get(User, c2.id)
        # Open two claims; they coexist as 'open'.
        cl1 = claim_svc.open_claim(s, item_id=item_id, claimant=u_c1, answers=["a1", "a2"])
        cl2 = claim_svc.open_claim(s, item_id=item_id, claimant=u_c2, answers=["b1", "b2"])
        # Approve the first.
        claim_svc.decide_claim(s, claim_id=cl1.id, by=u_f, approve=True)
        # Approving the second should fail.
        with pytest.raises(claim_svc.ClaimError):
            claim_svc.decide_claim(s, claim_id=cl2.id, by=u_f, approve=True)


def test_rejected_claim_counts_toward_attempts():
    finder = _make_user("+8801788888881")
    claimant = _make_user("+8801788888882")
    item_id = _make_item(finder)
    with session_scope() as s:
        u_f = s.get(User, finder.id)
        u_c = s.get(User, claimant.id)
        for i in range(claim_svc.ATTEMPTS_PER_ITEM):
            cl = claim_svc.open_claim(s, item_id=item_id, claimant=u_c, answers=["a1", "a2"])
            claim_svc.decide_claim(s, claim_id=cl.id, by=u_f, approve=False, reason="nope")
        with pytest.raises(claim_svc.ClaimError):
            claim_svc.open_claim(s, item_id=item_id, claimant=u_c, answers=["a1", "a2"])
