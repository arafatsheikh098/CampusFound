"""Audit log capture for M8 events: account status changes, item
hide/restore, report filed/resolved."""
from __future__ import annotations

from datetime import date, datetime

from sqlmodel import select

from app.auth import service as auth_svc
from app.db import session_scope
from app.items import service as item_svc
from app.models.audit import AuditLog
from app.models.category import Category
from app.models.place import Place
from app.models.report import ReportTarget
from app.models.user import AccountStatus, User
from app.moderation import service as mod_svc


def _user(mobile, *, mod=False, status=AccountStatus.APPROVED):
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


def _actions() -> list[str]:
    with session_scope() as s:
        return [r.action for r in s.exec(select(AuditLog)).all()]


def test_suspend_writes_audit_action():
    mod = _user("+8801700000001", mod=True)
    target = _user("+8801700000002")
    with session_scope() as s:
        m = s.get(User, mod.id)
        t = s.get(User, target.id)
        mod_svc.set_account_status(s, user=t, new_status=AccountStatus.SUSPENDED, by=m)
    assert "account_status_changed" in _actions()


def test_hide_and_restore_write_audit():
    mod = _user("+8801700000003", mod=True)
    target = _user("+8801700000004")
    with session_scope() as s:
        c = Category(name="C", sensitive=False, is_active=True)
        p = Place(name="P", is_active=True)
        s.add(c)
        s.add(p)
        s.commit()
        s.refresh(c)
        s.refresh(p)
        u = s.get(User, target.id)
        item = item_svc.create_item(
            s, finder=u, category_id=c.id, place_id=p.id,
            date_found=date.today(), description="x", handover_note="",
            custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        m = s.get(User, mod.id)
        it = s.get(__import__("app.models.item", fromlist=["FoundItem"]).FoundItem, item.id)
        mod_svc.hide_item(s, item=it, by=m)
        mod_svc.restore_item(s, item=it, by=m)
    actions = _actions()
    assert "item_hidden" in actions
    assert "item_restored" in actions


def test_report_filed_writes_audit():
    target = _user("+8801700000005")
    with session_scope() as s:
        u = s.get(User, target.id)
        mod_svc.file_report(
            s, by=u, target_kind=ReportTarget.FOUND_ITEM, target_id=99,
            reason="spam",
        )
    actions = _actions()
    assert "report_filed" in actions
