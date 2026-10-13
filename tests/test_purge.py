"""Privacy operations: purge and delete-my-data CLI commands."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from freezegun import freeze_time

from app import cli
from app.audit import write_audit
from app.auth import service as auth_svc
from app.db import session_scope
from app.items import service as item_svc
from app.models.audit import AuditLog
from app.models.category import Category
from app.models.item import FoundItem, ItemStatus
from app.models.place import Place
from app.models.user import AccountStatus, User
from sqlmodel import select


def _user(mobile, mod=False, status=AccountStatus.APPROVED):
    with session_scope() as s:
        u = auth_svc.signup(
            s, full_name="X", department="CSE", batch_or_session="2024",
            mobile=mobile, password="password123",
            is_member_confirmed=True, is_adult_confirmed=True,
        )
        u.status = status
        u.is_moderator = mod
        if mod:
            u.approved_at = datetime.utcnow()
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


def _setup_with_terminal_item():
    u = _user("+8801711111111")
    with session_scope() as s:
        c = Category(name="C", sensitive=False, is_active=True)
        p = Place(name="P", is_active=True)
        s.add(c)
        s.add(p)
        s.commit()
        s.refresh(c)
        s.refresh(p)
        uu = s.get(User, u.id)
        item = item_svc.create_item(
            s, finder=uu, category_id=c.id, place_id=p.id,
            date_found=date.today(), description="x", handover_note="",
            custody_requested="finder",
            questions=["q"], answers=["a"],
        )
    return u, item


def test_purge_drops_old_returned_items():
    u, item = _setup_with_terminal_item()
    # Mark the item as returned, way in the past.
    with session_scope() as s:
        it = s.get(FoundItem, item.id)
        it.status = ItemStatus.RETURNED
        it.returned_at = datetime.utcnow() - timedelta(days=120)
        s.add(it)
        s.commit()
    rc = cli.main(["purge"])
    assert rc == 0
    with session_scope() as s:
        rows = s.exec(select(FoundItem).where(FoundItem.id == item.id)).all()
        assert rows == []


def test_purge_keeps_recent_returned_items():
    u, item = _setup_with_terminal_item()
    with session_scope() as s:
        it = s.get(FoundItem, item.id)
        it.status = ItemStatus.RETURNED
        it.returned_at = datetime.utcnow() - timedelta(days=10)
        s.add(it)
        s.commit()
    cli.main(["purge"])
    with session_scope() as s:
        rows = s.exec(select(FoundItem).where(FoundItem.id == item.id)).all()
        assert len(rows) == 1


def test_purge_drops_old_rejected_users():
    u = _user("+8801700000002", status=AccountStatus.REJECTED)
    with session_scope() as s:
        uu = s.get(User, u.id)
        uu.created_at = datetime.utcnow() - timedelta(days=200)
        s.add(uu)
        s.commit()
    cli.main(["purge"])
    with session_scope() as s:
        rows = s.exec(select(User).where(User.id == u.id)).all()
        assert rows == []


def test_purge_keeps_recent_rejected_users():
    u = _user("+8801700000003", status=AccountStatus.REJECTED)
    cli.main(["purge"])
    with session_scope() as s:
        rows = s.exec(select(User).where(User.id == u.id)).all()
        assert len(rows) == 1


def test_purge_does_not_touch_audit_log():
    u, _ = _setup_with_terminal_item()
    with session_scope() as s:
        write_audit(s, actor_id=u.id, actor_label=u.full_name,
                    action="unique_action_xyz", target_kind="x", target_id=1)
        s.commit()
        # The new audit row exists.
        rows = s.exec(
            select(AuditLog).where(AuditLog.action == "unique_action_xyz")
        ).all()
        assert len(rows) == 1
        write_id = rows[0].id
    cli.main(["purge"])
    with session_scope() as s:
        rows = s.exec(
            select(AuditLog).where(AuditLog.action == "unique_action_xyz")
        ).all()
        assert len(rows) == 1
        assert rows[0].id == write_id
