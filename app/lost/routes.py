"""Lost report routes: create, view, withdraw, mark found."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.deps import check_csrf, get_current_user_optional, require_member
from app.lost import service as lost_svc
from app.matching.suggest import suggest_for_lost_report
from app.models.category import Category
from app.models.lost_report import LostReport
from app.models.place import Place
from app.models.report import ReportTarget
from app.models.user import User
from app.moderation import service as mod_svc

router = APIRouter()


@router.get("/lost", response_class=HTMLResponse)
def list_lost(
    request: Request,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(LostReport)
        .where(LostReport.is_open.is_(True))
        .order_by(LostReport.created_at.desc())
    ).all()
    return request.app.state.render(
        request,
        "lost/list.html",
        {"reports": rows, "current_user": user, "own_only": False},
    )


@router.get("/lost/mine", response_class=HTMLResponse)
def my_lost(
    request: Request,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(LostReport)
        .where(LostReport.owner_id == user.id)
        .order_by(LostReport.created_at.desc())
    ).all()
    return request.app.state.render(
        request,
        "lost/list.html",
        {"reports": rows, "current_user": user, "own_only": True},
    )


@router.get("/lost/new", response_class=HTMLResponse)
def new_lost_form(
    request: Request,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    cats = session.exec(select(Category).where(Category.is_active.is_(True)).order_by(Category.name)).all()
    places = session.exec(select(Place).where(Place.is_active.is_(True)).order_by(Place.name)).all()
    return request.app.state.render(
        request,
        "lost/new.html",
        {"categories": cats, "places": places, "current_user": user, "form": {}, "error": None},
    )


@router.post("/lost", response_class=HTMLResponse)
async def create_lost(
    request: Request,
    category_id: int = Form(...),
    place_id: int = Form(...),
    date_lost: str = Form(...),
    description: str = Form(...),
    private_note: str = Form(""),
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    try:
        d = date.fromisoformat(date_lost)
    except ValueError:
        raise HTTPException(400, "date_lost must be YYYY-MM-DD")
    try:
        report = lost_svc.create_lost_report(
            session,
            owner=user,
            category_id=category_id,
            place_id=place_id,
            date_lost=d,
            description=description,
            private_note=private_note,
        )
    except lost_svc.LostReportError as e:
        cats = session.exec(select(Category).where(Category.is_active.is_(True)).order_by(Category.name)).all()
        places = session.exec(select(Place).where(Place.is_active.is_(True)).order_by(Place.name)).all()
        return request.app.state.render(
            request,
            "lost/new.html",
            {
                "categories": cats,
                "places": places,
                "current_user": user,
                "form": {
                    "category_id": category_id,
                    "place_id": place_id,
                    "date_lost": date_lost,
                    "description": description,
                    "private_note": private_note,
                },
                "error": str(e),
            },
            status_code=400,
        )
    return RedirectResponse(url=f"/lost/{report.id}", status_code=302)


@router.get("/lost/{report_id}", response_class=HTMLResponse)
def view_lost(
    request: Request,
    report_id: int,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    report = session.get(LostReport, report_id)
    if report is None:
        raise HTTPException(404, "report not found")
    matches = suggest_for_lost_report(session, report, user)
    return request.app.state.render(
        request,
        "lost/view.html",
        {"report": report, "matches": matches, "current_user": user},
    )


@router.post("/lost/{report_id}/withdraw")
async def withdraw_lost(
    request: Request,
    report_id: int,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    report = session.get(LostReport, report_id)
    if report is None:
        raise HTTPException(404, "report not found")
    try:
        lost_svc.withdraw_lost_report(session, report=report, by=user)
    except lost_svc.LostReportError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url="/lost/mine", status_code=302)


@router.post("/lost/{report_id}/mark-found")
async def mark_found(
    request: Request,
    report_id: int,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    report = session.get(LostReport, report_id)
    if report is None:
        raise HTTPException(404, "report not found")
    try:
        lost_svc.mark_found(session, report=report, by=user)
    except lost_svc.LostReportError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url="/lost/mine", status_code=302)


@router.post("/lost/{report_id}/report")
async def report_lost(
    request: Request,
    report_id: int,
    reason: str = Form(...),
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    report = session.get(LostReport, report_id)
    if report is None:
        raise HTTPException(404, "report not found")
    try:
        mod_svc.file_report(
            session,
            by=user,
            target_kind=ReportTarget.LOST_REPORT,
            target_id=report.id,
            reason=reason,
        )
    except mod_svc.ModError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url=f"/lost/{report.id}", status_code=302)
