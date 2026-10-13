"""Telegram webhook + linking.

The webhook is registered at ``/telegram/webhook`` (POST). It uses
the ``X-Telegram-Bot-Api-Secret-Token`` header to authenticate
itself (the header is configured via the env
``TELEGRAM_WEBHOOK_SECRET``).

The webhook handler:
  - validates the secret token
  - extracts ``chat.id`` and ``text`` from the update
  - if the message starts with ``/start <code>`` and the code
    matches a user, binds the chat to that user
"""
from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_session
from app.models.user import User
from app.notifications import service as notif_svc

router = APIRouter()


def _verify_secret(provided: str) -> bool:
    settings = get_settings()
    if not settings.telegram_webhook_secret:
        return False
    expected = settings.telegram_webhook_secret
    return hmac.compare_digest(provided or "", expected)


@router.post("/telegram/webhook")
async def webhook(
    request: Request,
    session: Session = Depends(get_session),
):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not _verify_secret(secret):
        raise HTTPException(403, "invalid secret token")
    body = await request.body()
    try:
        update = json.loads(body or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "invalid json")

    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    if chat_id is None or not text:
        return {"ok": True}

    if text.startswith("/start "):
        code = text.split(None, 1)[1].strip()
        user = session.exec(
            select(User).where(User.telegram_link_code == code)
        ).one_or_none()
        if user is not None:
            notif_svc.bind_telegram_chat(session, user, int(chat_id))
    return {"ok": True}
