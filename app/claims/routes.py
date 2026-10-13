"""Claims routes: open, review, approve, reject, cancel, confirm.

All write paths require an approved member and a valid CSRF token.
The ``/claims/{id}/review`` page is only accessible to the custodian
(finder or moderator); the ``/claims/{id}`` view hides the private
answers from the claimant.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.claims import service as claim_svc
from app.db import get_session
from app.deps import check_csrf, get_current_user_optional, require_member
from app.models.claim import Claim, ClaimStatus
from app.models.category import Category
from app.models.item import FoundItem
from app.models.place import Place
from app.models.report import ReportTarget
from app.models.user import User
from app.moderation import service as mod_svc

router = APIRouter()


@router.get("/items/{item_id}/claim", response_class=HTMLResponse)
def new_claim_form(
    request: Request,
    item_id: int,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    item = session.get(FoundItem, item_id)
    if item is None or item.hidden or item.status.value not in ("open", "claim_approved"):
        return request.app.state.render(
            request, "items/not_found.html", {"current_user": user}, status_code=404
        )
    qs = sorted(item.questions, key=lambda x: x.position)
    return request.app.state.render(
        request,
        "claims/new.html",
        {"item": item, "questions": qs, "current_user": user, "error": None},
    )


@router.post("/items/{item_id}/claim", response_class=HTMLResponse)
async def submit_claim(
    request: Request,
    item_id: int,
    note: str = Form(""),
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    item = session.get(FoundItem, item_id)
    if item is None:
        raise HTTPException(404, "item not found")
    form = await request.form()
    answers: List[str] = []
    qs = sorted(item.questions, key=lambda x: x.position)
    for q in qs:
        answers.append(form.get(f"a{q.id}", ""))
    try:
        claim = claim_svc.open_claim(
            session,
            item_id=item_id,
            claimant=user,
            answers=answers,
            note=note,
        )
    except claim_svc.ClaimError as e:
        return request.app.state.render(
            request,
            "claims/new.html",
            {"item": item, "questions": qs, "current_user": user, "error": str(e)},
            status_code=400,
        )
    return RedirectResponse(url=f"/claims/{claim.id}", status_code=302)


@router.get("/claims/{claim_id}", response_class=HTMLResponse)
def view_claim(
    request: Request,
    claim_id: int,
    user: Optional[User] = Depends(get_current_user_optional),
    session: Session = Depends(get_session),
):
    if user is None or user.status.value != "approved":
        return RedirectResponse(url="/login", status_code=302)
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(404, "claim not found")
    item = session.get(FoundItem, claim.item_id)
    if item is None:
        raise HTTPException(404, "item not found")
    is_custodian = (user.id == item.finder_id) or user.is_moderator
    is_claimant = user.id == claim.claimant_id
    if not (is_custodian or is_claimant):
        raise HTTPException(403, "not allowed")
    qs = sorted(item.questions, key=lambda x: x.position)
    answers_by_qid = {a.question_id: a.answer for a in claim.answers}
    return request.app.state.render(
        request,
        "claims/view.html",
        {
            "claim": claim,
            "item": item,
            "questions": qs,
            "answers_by_qid": answers_by_qid,
            "is_custodian": is_custodian,
            "is_claimant": is_claimant,
            "current_user": user,
        },
    )


@router.get("/claims/{claim_id}/review", response_class=HTMLResponse)
def review_claim(
    request: Request,
    claim_id: int,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(404, "claim not found")
    item = session.get(FoundItem, claim.item_id)
    if item is None:
        raise HTTPException(404, "item not found")
    if not (user.id == item.finder_id or user.is_moderator):
        raise HTTPException(403, "not allowed")
    qs = sorted(item.questions, key=lambda x: x.position)
    answers_by_qid = {a.question_id: a.answer for a in claim.answers}
    claimant = session.get(User, claim.claimant_id)
    return request.app.state.render(
        request,
        "claims/review.html",
        {
            "claim": claim,
            "item": item,
            "questions": qs,
            "answers_by_qid": answers_by_qid,
            "claimant": claimant,
            "current_user": user,
        },
    )


@router.post("/claims/{claim_id}/approve")
async def approve_claim(
    request: Request,
    claim_id: int,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    try:
        claim_svc.decide_claim(session, claim_id=claim_id, by=user, approve=True)
    except claim_svc.ClaimError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url=f"/claims/{claim_id}", status_code=302)


@router.post("/claims/{claim_id}/reject")
async def reject_claim(
    request: Request,
    claim_id: int,
    reason: str = Form(""),
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    try:
        claim_svc.decide_claim(session, claim_id=claim_id, by=user, approve=False, reason=reason)
    except claim_svc.ClaimError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url=f"/claims/{claim_id}", status_code=302)


@router.post("/claims/{claim_id}/cancel")
async def cancel_claim(
    request: Request,
    claim_id: int,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    try:
        claim_svc.cancel_claim(session, claim_id=claim_id, by=user)
    except claim_svc.ClaimError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url=f"/items/{session.get(Claim, claim_id).item_id}", status_code=302)


@router.post("/claims/{claim_id}/confirm-returned")
async def confirm_returned(
    request: Request,
    claim_id: int,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    try:
        claim_svc.confirm_returned(session, claim_id=claim_id, by=user)
    except claim_svc.ClaimError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url=f"/claims/{claim_id}", status_code=302)


@router.post("/claims/{claim_id}/report")
async def report_claim(
    request: Request,
    claim_id: int,
    reason: str = Form(...),
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(404, "claim not found")
    try:
        mod_svc.file_report(
            session,
            by=user,
            target_kind=ReportTarget.CLAIM,
            target_id=claim.id,
            reason=reason,
        )
    except mod_svc.ModError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url=f"/claims/{claim.id}", status_code=302)
