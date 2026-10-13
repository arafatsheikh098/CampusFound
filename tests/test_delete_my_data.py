"""delete-my-data CLI: removes every row tied to a mobile, leaves a
trace in the audit log for historical accountability (F8).
"""
from __future__ import annotations

from datetime import date

from sqlmodel import select

from app import cli
from app.audit import write_audit
from app.auth import service as auth_svc
from app.claims import service as claim_svc
from app.db import session_scope
from app.items import service as item_svc
from app.lost import service as lost_svc
from app.models.audit import AuditLog
from app.models.category import Category
from app.models.claim import Claim
from app.models.item import FoundItem
from app.models.lost_report import LostReport
from app.models.place import Place
from app.models.user import AccountStatus, User


def _user(mobile, status=AccountStatus.APPROVED):
    with session_scope() as s:
        u = auth_svc.signup(
            s, full_name="Del", department="CSE", batch_or_session="2024",
            mobile=mobile, password="password123",
            is_member_confirmed=True, is_adult_confirmed=True,
        )
        u.status = status
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


def test_delete_my_data_removes_user_and_items_and_claims_and_lost_reports():
    target = _user("+8801755555555")
    finder = _user("+8801766666666")
    with session_scope() as s:
        c = Category(name="C", sensitive=False, is_active=True)
        p = Place(name="P", is_active=True)
        s.add(c)
        s.add(p)
        s.commit()
        s.refresh(c)
        s.refresh(p)
        u_t = s.get(User, target.id)
        u_f = s.get(User, finder.id)
        # Target's item (also as finder)
        item1 = item_svc.create_item(
            s, finder=u_t, category_id=c.id, place_id=p.id,
            date_found=date.today(), description="x", handover_note="",
            custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        # Claim by target on finder's item
        item2 = item_svc.create_item(
            s, finder=u_f, category_id=c.id, place_id=p.id,
            date_found=date.today(), description="y", handover_note="",
            custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        claim_svc.open_claim(s, item_id=item2.id, claimant=u_t, answers=["a"])
        # Target's lost report
        lost_svc.create_lost_report(
            s, owner=u_t, category_id=c.id, place_id=p.id,
            date_lost=date.today(), description="lost it", private_note="private",
        )

    rc = cli.main(["delete-my-data", "--mobile", "+8801755555555"])
    assert rc == 0

    with session_scope() as s:
        assert s.get(User, target.id) is None
        assert s.get(FoundItem, item1.id) is None
        # Item 2 (the finder's) still exists; the claim is gone.
        assert s.get(FoundItem, item2.id) is not None
        claims = s.exec(select(Claim).where(Claim.claimant_id == target.id)).all()
        assert claims == []
        lost = s.exec(select(LostReport).where(LostReport.owner_id == target.id)).all()
        assert lost == []


def test_delete_my_data_writes_audit_row():
    target = _user("+8801777777777")
    with session_scope() as s:
        before = len(s.exec(
            select(AuditLog).where(AuditLog.action == "user_data_deleted")
        ).all())
    cli.main(["delete-my-data", "--mobile", "+8801777777777"])
    with session_scope() as s:
        rows = s.exec(
            select(AuditLog).where(AuditLog.action == "user_data_deleted")
        ).all()
        assert len(rows) == before + 1
        r = rows[-1]
        # The audit row holds a snapshot of the mobile, with actor_label
        # identifying the user.
        assert "deleted_user" in r.actor_label
        assert "+8801777777777" in r.extra_json


def test_delete_my_data_unknown_mobile_returns_2():
    rc = cli.main(["delete-my-data", "--mobile", "+8801799999999"])
    assert rc == 2
