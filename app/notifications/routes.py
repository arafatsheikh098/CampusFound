"""In-app notification routes: list, mark-all-read, telegram link."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.deps import check_csrf, require_member
from app.models.notification import Notification
from app.models.user import User
from app.notifications import service as notif_svc

router = APIRouter()


def _payload_of(n: Notification) -> dict:
    try:
        return json.loads(n.payload_json or "{}")
    except (TypeError, ValueError):
        return {}


@router.get("/notifications", response_class=HTMLResponse)
def list_notifications(
    request: Request,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
    ).all()
    enriched = [
        {
            "id": n.id,
            "kind": n.kind,
            "payload": _payload_of(n),
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in rows
    ]
    code = user.telegram_link_code or ""
    return request.app.state.render(
        request,
        "notifications/list.html",
        {
            "notifications": enriched,
            "current_user": user,
            "telegram_link_code": code,
            "telegram_enabled": request.app.state.settings.telegram_enabled,
        },
    )


@router.post("/notifications/read-all")
async def read_all(
    request: Request,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    notif_svc.mark_all_read(session, user.id)
    return RedirectResponse(url="/notifications", status_code=302)


@router.post("/notifications/telegram-link")
async def telegram_link(
    request: Request,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    """Generate a one-time code for linking a Telegram chat."""
    await check_csrf(request)
    code = notif_svc.new_link_code()
    user.telegram_link_code = code
    session.add(user)
    session.commit()
    return RedirectResponse(url="/notifications", status_code=302)
