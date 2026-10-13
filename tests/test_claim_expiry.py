"""Approved claim expiry test (F7) — verified in test_handover.py too,
this is the boundary test using freezegun."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from freezegun import freeze_time

from app.auth import service as auth_svc
from app.claims import service as claim_svc
from app.config import get_settings
from app.db import session_scope
from app.items import service as item_svc
from app.models.category import Category
from app.models.claim import Claim, ClaimStatus
from app.models.item import FoundItem
from app.models.place import Place
from app.models.user import AccountStatus, User


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


def test_approved_claim_at_exactly_window_is_still_approved():
    finder = _user("+8801711111111")
    claimant = _user("+8801722222222")
    with freeze_time("2026-04-01"):
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
                date_found=date.today(), description="x",
                handover_note="", custody_requested="finder",
                questions=["q"], answers=["a"],
            )
            cl = claim_svc.open_claim(s, item_id=item.id, claimant=u_c, answers=["a"])
            claim_svc.decide_claim(s, claim_id=cl.id, by=u_f, approve=True)
    window = get_settings().days_claim_expiry
    with freeze_time("2026-04-01") as frozen:
        frozen.tick(delta=timedelta(days=window))
        with session_scope() as s:
            claim_svc.sweep_expired(s)
        with session_scope() as s:
            row = s.get(Claim, cl.id)
            # At the boundary, the claim is still approved
            assert row.status == ClaimStatus.APPROVED
    with freeze_time("2026-04-01") as frozen:
        frozen.tick(delta=timedelta(days=window + 1))
        with session_scope() as s:
            claim_svc.sweep_expired(s)
        with session_scope() as s:
            row = s.get(Claim, cl.id)
            assert row.status == ClaimStatus.EXPIRED
