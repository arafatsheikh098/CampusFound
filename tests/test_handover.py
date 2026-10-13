"""Handover + contact-reveal tests — F7."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from freezegun import freeze_time

from app.auth import service as auth_svc
from app.claims import service as claim_svc
from app.db import session_scope
from app.items import service as item_svc
from app.models.category import Category
from app.models.claim import ClaimStatus
from app.models.item import FoundItem
from app.models.photo import Photo
from app.models.place import Place
from app.models.user import AccountStatus, User
from app.photos.processing import synthesise_test_png
from app.photos.service import attach_photos


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


def _item_with_photo(finder):
    with session_scope() as s:
        c = Category(name="C", sensitive=False, is_active=True)
        p = Place(name="P", is_active=True)
        s.add(c)
        s.add(p)
        s.commit()
        s.refresh(c)
        s.refresh(p)
        u_f = s.get(User, finder.id)
        item = item_svc.create_item(
            s, finder=u_f, category_id=c.id, place_id=p.id,
            date_found=date.today(), description="x",
            handover_note="Library desk 10-13",
            custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        attach_photos(s, item=item, uploads=[(synthesise_test_png(64, 64), "a.png")], by=u_f)
        s.commit()
        return item.id


def test_both_confirm_returned_marks_item_and_deletes_photos():
    finder = _user("+8801711111111")
    claimant = _user("+8801722222222")
    item_id = _item_with_photo(finder)
    with session_scope() as s:
        u_f = s.get(User, finder.id)
        u_c = s.get(User, claimant.id)
        cl = claim_svc.open_claim(s, item_id=item_id, claimant=u_c, answers=["a"])
        claim_svc.decide_claim(s, claim_id=cl.id, by=u_f, approve=True)
        claim_svc.confirm_returned(s, claim_id=cl.id, by=u_c)
        claim_svc.confirm_returned(s, claim_id=cl.id, by=u_f)
    with session_scope() as s:
        item = s.get(FoundItem, item_id)
        assert item.status.value == "returned"
        photos = s.exec(__import__("sqlmodel").select(Photo).where(Photo.item_id == item_id)).all()
        assert photos == []


def test_approved_claim_expires_after_window():
    finder = _user("+8801733333333")
    claimant = _user("+8801744444444")
    item_id = _item_with_photo(finder)
    with freeze_time("2026-04-01") as frozen:
        with session_scope() as s:
            u_f = s.get(User, finder.id)
            u_c = s.get(User, claimant.id)
            cl = claim_svc.open_claim(s, item_id=item_id, claimant=u_c, answers=["a"])
            claim_svc.decide_claim(s, claim_id=cl.id, by=u_f, approve=True)
        # 6 days later, the claim is still approved
        frozen.tick(delta=timedelta(days=6))
        with session_scope() as s:
            claim_svc.sweep_expired(s)
        with session_scope() as s:
            from sqlmodel import select
            claim = s.exec(select(__import__("app.models.claim", fromlist=["Claim"]).Claim).where(
                __import__("app.models.claim", fromlist=["Claim"]).Claim.id == cl.id
            )).one()
            assert claim.status == ClaimStatus.APPROVED
        # 8 days after approval, the claim is expired
        frozen.tick(delta=timedelta(days=2))
        with session_scope() as s:
            claim_svc.sweep_expired(s)
        with session_scope() as s:
            from sqlmodel import select
            claim = s.exec(select(__import__("app.models.claim", fromlist=["Claim"]).Claim).where(
                __import__("app.models.claim", fromlist=["Claim"]).Claim.id == cl.id
            )).one()
            assert claim.status == ClaimStatus.EXPIRED
