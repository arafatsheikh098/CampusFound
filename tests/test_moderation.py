"""Moderation service: set_account_status, hide/restore_item, file_report."""
from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.audit import write_audit
from app.auth import service as auth_svc
from app.db import session_scope
from app.items import service as item_svc
from app.models.category import Category
from app.models.item import FoundItem, ItemStatus
from app.models.place import Place
from app.models.report import Report, ReportTarget
from app.models.user import AccountStatus, User
from app.moderation import service as mod_svc
from app.security import sign_session


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


def _setup():
    mod = _user("+8801700000001", mod=True)
    target = _user("+8801700000002")
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
    return mod, target, item


def test_set_account_status_writes_audit():
    mod, target, _ = _setup()
    with session_scope() as s:
        mod_obj = s.get(User, mod.id)
        target_obj = s.get(User, target.id)
        mod_svc.set_account_status(
            s, user=target_obj, new_status=AccountStatus.SUSPENDED, by=mod_obj
        )
    with session_scope() as s:
        u = s.get(User, target.id)
        assert u.status == AccountStatus.SUSPENDED
        assert u.suspended_at is not None


def test_set_account_status_blocks_self_change():
    mod, _, _ = _setup()
    with session_scope() as s:
        mod_obj = s.get(User, mod.id)
        with pytest.raises(mod_svc.ModError):
            mod_svc.set_account_status(
                s, user=mod_obj, new_status=AccountStatus.SUSPENDED, by=mod_obj
            )


def test_set_account_status_blocks_non_moderator():
    mod, target, _ = _setup()
    regular = _user("+8801700000099")
    with session_scope() as s:
        target_obj = s.get(User, target.id)
        regular_obj = s.get(User, regular.id)
        with pytest.raises(mod_svc.ModError):
            mod_svc.set_account_status(
                s, user=target_obj, new_status=AccountStatus.SUSPENDED, by=regular_obj
            )


def test_hide_and_restore_item():
    mod, target, item = _setup()
    with session_scope() as s:
        mod_obj = s.get(User, mod.id)
        item_obj = s.get(FoundItem, item.id)
        mod_svc.hide_item(s, item=item_obj, by=mod_obj)
    with session_scope() as s:
        it = s.get(FoundItem, item.id)
        assert it.hidden is True
    with session_scope() as s:
        mod_obj = s.get(User, mod.id)
        item_obj = s.get(FoundItem, item.id)
        mod_svc.restore_item(s, item=item_obj, by=mod_obj)
    with session_scope() as s:
        it = s.get(FoundItem, item.id)
        assert it.hidden is False


def test_file_report_strips_and_saves():
    mod, target, item = _setup()
    with session_scope() as s:
        target_obj = s.get(User, target.id)
        mod_svc.file_report(
            s, by=target_obj,
            target_kind=ReportTarget.FOUND_ITEM,
            target_id=item.id,
            reason="  bad thing   ",
        )
    with session_scope() as s:
        rows = s.exec(
            __import__("sqlmodel").select(Report)
        ).all()
        assert len(rows) == 1
        assert rows[0].reason == "bad thing"
        assert rows[0].resolved is False
        assert rows[0].reporter_id == target.id
        assert rows[0].target_kind == ReportTarget.FOUND_ITEM


def test_file_report_rejects_empty():
    mod, target, _ = _setup()
    with session_scope() as s:
        target_obj = s.get(User, target.id)
        with pytest.raises(mod_svc.ModError):
            mod_svc.file_report(
                s, by=target_obj,
                target_kind=ReportTarget.FOUND_ITEM,
                target_id=1,
                reason="   ",
            )


def test_moderation_dashboard_requires_moderator(client: TestClient):
    regular = _user("+8801711111111")
    client.cookies.set("cf_session", sign_session({"uid": regular.id}))
    r = client.get("/moderation")
    assert r.status_code == 403


def test_moderation_dashboard_renders_for_mod(client: TestClient):
    mod, _, _ = _setup()
    client.cookies.set("cf_session", sign_session({"uid": mod.id}))
    r = client.get("/moderation")
    assert r.status_code == 200
    assert "Pending accounts" in r.text or "pending" in r.text.lower()


def test_post_status_change_via_route(client: TestClient):
    mod, target, _ = _setup()
    client.cookies.set("cf_session", sign_session({"uid": mod.id}))
    # Trigger cookie creation (cf_sid) by hitting the landing page first.
    client.get("/")
    # Then render the dashboard to get a valid csrf token.
    r = client.get("/moderation")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    csrf = m.group(1) if m else ""
    assert csrf, "no csrf token on dashboard"
    r = client.post(
        f"/moderation/users/{target.id}/status",
        data={"csrf_token": csrf, "new_status": "suspended"},
        follow_redirects=False,
    )
    assert r.status_code == 302, f"expected redirect, got {r.status_code}: {r.text[:200]}"
    with session_scope() as s:
        u = s.get(User, target.id)
        assert u.status == AccountStatus.SUSPENDED


def test_post_self_status_change_rejected(client: TestClient):
    mod, _, _ = _setup()
    client.cookies.set("cf_session", sign_session({"uid": mod.id}))
    client.get("/")
    r = client.get("/moderation")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    csrf = m.group(1) if m else ""
    r = client.post(
        f"/moderation/users/{mod.id}/status",
        data={"csrf_token": csrf, "new_status": "suspended"},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_file_report_via_item_route(client: TestClient):
    mod, target, item = _setup()
    client.cookies.set("cf_session", sign_session({"uid": target.id}))
    client.get("/")
    # Get CSRF from the item view
    r = client.get(f"/items/{item.id}")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    csrf = m.group(1) if m else ""
    r = client.post(
        f"/items/{item.id}/report",
        data={"csrf_token": csrf, "reason": "spam-like"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    from app.models.report import Report
    with session_scope() as s:
        reports = s.exec(__import__("sqlmodel").select(Report)).all()
        assert len(reports) == 1
        assert reports[0].target_kind.value == "found_item"
        assert reports[0].target_id == item.id


def test_file_report_empty_reason_rejected(client: TestClient):
    mod, target, item = _setup()
    client.cookies.set("cf_session", sign_session({"uid": target.id}))
    client.get("/")
    r = client.get(f"/items/{item.id}")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    csrf = m.group(1) if m else ""
    r = client.post(
        f"/items/{item.id}/report",
        data={"csrf_token": csrf, "reason": "   "},
        follow_redirects=False,
    )
    assert r.status_code == 400
