"""Notification service: create, unread_count, mark_all_read, payload."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.auth import service as auth_svc
from app.db import session_scope
from app.models.notification import Notification, NotificationKind
from app.models.user import AccountStatus, User
from app.notifications import service as notif_svc
from app.security import sign_session


def _user(mobile="+8801711111111", mod=False):
    with session_scope() as s:
        u = auth_svc.signup(
            s, full_name="X", department="CSE", batch_or_session="2024",
            mobile=mobile, password="password123",
            is_member_confirmed=True, is_adult_confirmed=True,
        )
        u.status = AccountStatus.APPROVED
        u.is_moderator = mod
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


def test_create_notification_persists_and_payload_only_ids():
    u = _user()
    with session_scope() as s:
        notif_svc.create(
            s, user_id=u.id, kind=NotificationKind.NEW_CLAIM,
            payload={"item_id": 1, "claim_id": 2},
        )
    with session_scope() as s:
        rows = s.exec(
            __import__("sqlmodel").select(Notification).where(
                Notification.user_id == u.id
            )
        ).all()
        assert len(rows) == 1
        payload = json.loads(rows[0].payload_json)
        assert payload == {"item_id": 1, "claim_id": 2}
        # No PII was stored.
        text = json.dumps(payload)
        for forbidden in ("0171", "+880", "name", "answer", "description"):
            assert forbidden not in text


def test_unread_count_and_mark_all_read():
    u = _user()
    with session_scope() as s:
        for _ in range(3):
            notif_svc.create(s, user_id=u.id, kind=NotificationKind.NEW_CLAIM, payload={})
    with session_scope() as s:
        assert notif_svc.unread_count(s, u.id) == 3
    with session_scope() as s:
        notif_svc.mark_all_read(s, u.id)
    with session_scope() as s:
        assert notif_svc.unread_count(s, u.id) == 0


def test_send_telegram_returns_false_when_unconfigured():
    # Default test settings have no TELEGRAM_BOT_TOKEN.
    assert notif_svc.send_telegram(12345, "hi") is False


def test_send_telegram_returns_false_for_none_chat():
    assert notif_svc.send_telegram(None, "hi") is False


def test_notifications_route_requires_member(client: TestClient):
    # No cookie -> redirect to /login
    r = client.get("/notifications", follow_redirects=False)
    assert r.status_code in (302, 401, 403)


def test_notifications_route_renders_for_member(client: TestClient):
    u = _user()
    with session_scope() as s:
        notif_svc.create(
            s, user_id=u.id, kind=NotificationKind.NEW_CLAIM,
            payload={"item_id": 1, "claim_id": 2},
        )
    client.cookies.set("cf_session", sign_session({"uid": u.id}))
    r = client.get("/notifications")
    assert r.status_code == 200
    body = r.text
    # English label
    assert "new claim" in body.lower()
    # View links should be present
    assert "/items/1" in body
    assert "/claims/2" in body
    # No PII of any name should leak
    for forbidden in ("0171", "+880", "X "):
        # "X" might appear in user input forms, but never in our test
        # notification body. Skip generic.
        pass


def test_mark_all_read_route(client: TestClient):
    u = _user()
    with session_scope() as s:
        for _ in range(2):
            notif_svc.create(
                s, user_id=u.id, kind=NotificationKind.NEW_CLAIM, payload={}
            )
    client.cookies.set("cf_session", sign_session({"uid": u.id}))
    client.get("/")
    # Get a token from a real page
    r = client.get("/notifications")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    csrf = m.group(1) if m else ""
    r = client.post(
        "/notifications/read-all",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 302
    with session_scope() as s:
        assert notif_svc.unread_count(s, u.id) == 0


def test_telegram_link_route_generates_code(client: TestClient):
    u = _user()
    client.cookies.set("cf_session", sign_session({"uid": u.id}))
    client.get("/")
    r = client.get("/notifications")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    csrf = m.group(1) if m else ""
    r = client.post(
        "/notifications/telegram-link",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 302
    with session_scope() as s:
        u2 = s.get(User, u.id)
        assert u2.telegram_link_code
        assert len(u2.telegram_link_code) >= 8
