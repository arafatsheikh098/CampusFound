"""Moderation router.

Endpoints for moderator-only operations on accounts, items and reports.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.audit import write_audit
from app.db import get_session
from app.deps import check_csrf, require_moderator
from app.models.item import FoundItem
from app.models.report import Report
from app.models.user import AccountStatus, User
from app.moderation import service as mod_svc

router = APIRouter()


@router.get("/moderation", response_class=HTMLResponse)
def dashboard(
    request: Request,
    session: Session = Depends(get_session),
    mod: User = Depends(require_moderator),
):
    pending = session.exec(
        select(User).where(User.status == AccountStatus.PENDING).order_by(User.created_at)
    ).all()
    suspended = session.exec(
        select(User).where(User.status == AccountStatus.SUSPENDED).order_by(User.suspended_at.desc())
    ).all()
    reports = session.exec(
        select(Report).where(Report.resolved.is_(False)).order_by(Report.created_at.desc())
    ).all()
    return request.app.state.render(
        request,
        "moderation/dashboard.html",
        {
            "current_user": mod,
            "pending": pending,
            "suspended": suspended,
            "reports": reports,
        },
    )


@router.post("/moderation/users/{user_id}/status")
async def set_status(
    request: Request,
    user_id: int,
    new_status: str = Form(...),
    session: Session = Depends(get_session),
    mod: User = Depends(require_moderator),
):
    await check_csrf(request)
    try:
        target = AccountStatus(new_status)
    except ValueError:
        raise HTTPException(400, "invalid status")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    if user.id == mod.id:
        raise HTTPException(400, "you cannot change your own status")
    try:
        mod_svc.set_account_status(session, user=user, new_status=target, by=mod)
    except mod_svc.ModError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url="/moderation", status_code=302)


@router.post("/moderation/items/{item_id}/hide")
async def hide_item(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
    mod: User = Depends(require_moderator),
):
    await check_csrf(request)
    item = session.get(FoundItem, item_id)
    if item is None:
        raise HTTPException(404, "item not found")
    try:
        mod_svc.hide_item(session, item=item, by=mod)
    except mod_svc.ModError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url=f"/items/{item.id}", status_code=302)


@router.post("/moderation/items/{item_id}/restore")
async def restore_item(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
    mod: User = Depends(require_moderator),
):
    await check_csrf(request)
    item = session.get(FoundItem, item_id)
    if item is None:
        raise HTTPException(404, "item not found")
    try:
        mod_svc.restore_item(session, item=item, by=mod)
    except mod_svc.ModError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url=f"/items/{item.id}", status_code=302)


@router.post("/moderation/reports/{report_id}/resolve")
async def resolve_report(
    request: Request,
    report_id: int,
    session: Session = Depends(get_session),
    mod: User = Depends(require_moderator),
):
    await check_csrf(request)
    r = session.get(Report, report_id)
    if r is None:
        raise HTTPException(404, "report not found")
    r.resolved = True
    session.add(r)
    write_audit(
        session,
        actor_id=mod.id,
        actor_label=mod.full_name,
        action="report_resolved",
        target_kind=r.target_kind.value,
        target_id=r.target_id,
        extra={"report_id": r.id},
    )
    session.commit()
    return RedirectResponse(url="/moderation", status_code=302)
