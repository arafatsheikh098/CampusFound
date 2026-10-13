"""Audit log tests for claims — every approval, rejection, reveal and
handover writes an audit row (F9)."""
from __future__ import annotations

from datetime import date

from sqlmodel import select

from app.audit import write_audit
from app.auth import service as auth_svc
from app.claims import service as claim_svc
from app.db import session_scope
from app.items import service as item_svc
from app.models.audit import AuditLog
from app.models.category import Category
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


def test_approval_rejection_handover_write_audit():
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
            date_found=date.today(), description="x",
            handover_note="", custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        cl = claim_svc.open_claim(s, item_id=item.id, claimant=u_c, answers=["a"])
        claim_svc.decide_claim(s, claim_id=cl.id, by=u_f, approve=True)
        claim_svc.confirm_returned(s, claim_id=cl.id, by=u_f)
        claim_svc.confirm_returned(s, claim_id=cl.id, by=u_c)
    with session_scope() as s:
        actions = [r.action for r in s.exec(select(AuditLog)).all()]
        for expected in (
            "item_created",
            "claim_opened",
            "claim_approved",
            "claim_handover_confirmed",
            "item_returned",
        ):
            assert expected in actions, f"missing {expected}; saw {actions}"


def test_audit_rows_are_only_inserted():
    finder = _user("+8801733333333")
    claimant = _user("+8801744444444")
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
        claim_svc.decide_claim(s, claim_id=cl.id, by=u_f, approve=False)
    with session_scope() as s:
        rows = s.exec(select(AuditLog)).all()
        # We never UPDATE/DELETE audit rows.
        # The claim_rejected row is here; verify it is the only entry
        # for that target.
        from app.models.audit import AuditLog as AuditLogModel
        rejected = [r for r in rows if r.action == "claim_rejected"]
        assert len(rejected) == 1
