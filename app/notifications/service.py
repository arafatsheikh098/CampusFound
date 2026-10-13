"""Notification creation + Telegram delivery.

Notifications store *only* IDs in the payload (no names, no
numbers, no answers, no item text). The Telegram message is built
from the i18n key for the kind and contains no item details.

If TELEGRAM_BOT_TOKEN is not set, Telegram delivery is a no-op
and the in-app notification is still recorded.
"""
from __future__ import annotations

import json
import secrets
from typing import Any, Optional

import httpx
from sqlmodel import Session, select

from app.config import get_settings
from app.models.notification import Notification, NotificationKind
from app.models.user import User


def _payload(d: dict) -> str:
    return json.dumps(d or {}, separators=(",", ":"))[:500]


def create(
    session: Session,
    *,
    user_id: int,
    kind: NotificationKind,
    payload: Optional[dict] = None,
    commit: bool = True,
) -> Notification:
    n = Notification(
        user_id=user_id,
        kind=kind,
        payload_json=_payload(payload or {}),
    )
    session.add(n)
    if commit:
        session.commit()
        session.refresh(n)
    return n


def unread_count(session: Session, user_id: int) -> int:
    rows = session.exec(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    ).all()
    return len(rows)


def mark_all_read(session: Session, user_id: int) -> None:
    rows = session.exec(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    ).all()
    for n in rows:
        n.is_read = True
        session.add(n)
    session.commit()


def send_telegram(chat_id: int, text: str) -> bool:
    """Send a Telegram message. Returns True on success.

    If Telegram is not configured, returns False without raising.
    Network errors are swallowed and reported as False.
    """
    settings = get_settings()
    if not settings.telegram_enabled:
        return False
    if chat_id is None:
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        r = httpx.post(
            url,
            json={"chat_id": chat_id, "text": text},
            timeout=10.0,
        )
        return r.status_code == 200
    except Exception:
        return False


def new_link_code() -> str:
    return secrets.token_urlsafe(8)


def bind_telegram_chat(session: Session, user: User, chat_id: int) -> None:
    user.telegram_chat_id = chat_id
    user.telegram_link_code = None
    session.add(user)
    session.commit()
    create(
        session,
        user_id=user.id,
        kind=NotificationKind.TELEGRAM_LINKED,
        payload={},
    )
    if user.telegram_chat_id:
        send_telegram(user.telegram_chat_id, "CampusFound: linked.")
