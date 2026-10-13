"""Found-item routes: create, view, edit, withdraw."""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.deps import check_csrf, get_current_user_optional, require_member
from app.items import service as item_svc
from app.models.category import Category
from app.models.item import FoundItem
from app.models.place import Place
from app.models.user import User
from app.photos import service as photo_svc
from app.photos.processing import PhotoError

router = APIRouter()


def _ensure_member(user: User) -> None:
    if user is None or user.status.value != "approved":
        raise HTTPException(403, "approved members only")


@router.get("/items/new", response_class=HTMLResponse)
def new_item_form(
    request: Request,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    cats = session.exec(select(Category).where(Category.is_active.is_(True)).order_by(Category.name)).all()
    places = session.exec(select(Place).where(Place.is_active.is_(True)).order_by(Place.name)).all()
    return request.app.state.render(
        request,
        "items/new.html",
        {"categories": cats, "places": places, "current_user": user, "form": {}},
    )


@router.post("/items", response_class=HTMLResponse)
async def create_item(
    request: Request,
    category_id: int = Form(...),
    place_id: int = Form(...),
    date_found: str = Form(...),
    description: str = Form(...),
    handover_note: str = Form(""),
    custody: str = Form("finder"),
    q1: str = Form(""),
    a1: str = Form(""),
    q2: str = Form(""),
    a2: str = Form(""),
    q3: str = Form(""),
    a3: str = Form(""),
    photos: List[UploadFile] = File(default=[]),
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    try:
        d = date.fromisoformat(date_found)
    except ValueError:
        raise HTTPException(400, "date_found must be YYYY-MM-DD")
    questions = [q1, q2, q3]
    answers = [a1, a2, a3]
    has_photo = any(p is not None and p.filename for p in photos)
    try:
        item = item_svc.create_item(
            session,
            finder=user,
            category_id=category_id,
            place_id=place_id,
            date_found=d,
            description=description,
            handover_note=handover_note,
            custody_requested=custody,
            questions=questions,
            answers=answers,
            has_photo=has_photo,
        )
    except item_svc.ItemError as e:
        cats = session.exec(select(Category).where(Category.is_active.is_(True)).order_by(Category.name)).all()
        places = session.exec(select(Place).where(Place.is_active.is_(True)).order_by(Place.name)).all()
        return request.app.state.render(
            request,
            "items/new.html",
            {
                "categories": cats,
                "places": places,
                "current_user": user,
                "form": {
                    "category_id": category_id,
                    "place_id": place_id,
                    "date_found": date_found,
                    "description": description,
                    "handover_note": handover_note,
                    "custody": custody,
                    "q1": q1, "a1": a1, "q2": q2, "a2": a2, "q3": q3, "a3": a3,
                },
                "error": str(e),
            },
            status_code=400,
        )

    # Photo upload (best-effort; failures fall back to the form).
    if has_photo:
        try:
            uploads = []
            for f in photos:
                if not f or not f.filename:
                    continue
                uploads.append((f.file.read(), f.filename))
            photo_svc.attach_photos(session, item=item, uploads=uploads, by=user)
        except PhotoError as e:
            cats = session.exec(select(Category).where(Category.is_active.is_(True)).order_by(Category.name)).all()
            places = session.exec(select(Place).where(Place.is_active.is_(True)).order_by(Place.name)).all()
            return request.app.state.render(
                request,
                "items/new.html",
                {
                    "categories": cats,
                    "places": places,
                    "current_user": user,
                    "form": {
                        "category_id": category_id,
                        "place_id": place_id,
                        "date_found": date_found,
                        "description": description,
                        "handover_note": handover_note,
                        "custody": custody,
                        "q1": q1, "a1": a1, "q2": q2, "a2": a2, "q3": q3, "a3": a3,
                    },
                    "error": str(e),
                },
                status_code=400,
            )

    return RedirectResponse(url=f"/items/{item.id}", status_code=302)


@router.get("/items", response_class=HTMLResponse)
def list_items(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Stub list. Real search lands in M5."""
    if user is None or user.status.value != "approved":
        return RedirectResponse(url="/login", status_code=302)
    return request.app.state.render(
        request,
        "items/list.html",
        {"current_user": user},
    )


@router.get("/items/{item_id}", response_class=HTMLResponse)
def view_item(
    request: Request,
    item_id: int,
    user: Optional[User] = Depends(get_current_user_optional),
    session: Session = Depends(get_session),
):
    item = session.get(FoundItem, item_id)
    if item is None or item.hidden or item.status.value == "withdrawn":
        # Don't leak existence to non-owners
        return request.app.state.render(
            request,
            "items/not_found.html",
            {"current_user": user},
            status_code=404,
        )
    category = session.get(Category, item.category_id)
    place = session.get(Place, item.place_id)
    can_see_answers = (
        user is not None
        and (user.is_moderator or user.id == item.finder_id)
    )
    can_edit = user is not None and (user.is_moderator or user.id == item.finder_id)
    return request.app.state.render(
        request,
        "items/view.html",
        {
            "item": item,
            "category": category,
            "place": place,
            "current_user": user,
            "can_see_answers": can_see_answers,
            "can_edit": can_edit,
        },
    )


@router.get("/items/{item_id}/edit", response_class=HTMLResponse)
def edit_item_form(
    request: Request,
    item_id: int,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    item = session.get(FoundItem, item_id)
    if item is None:
        raise HTTPException(404, "item not found")
    if not (user.is_moderator or user.id == item.finder_id):
        raise HTTPException(403, "not allowed")
    if item.status.value in ("returned", "withdrawn", "unclaimed"):
        raise HTTPException(400, "item is no longer editable")
    cats = session.exec(select(Category).where(Category.is_active.is_(True)).order_by(Category.name)).all()
    places = session.exec(select(Place).where(Place.is_active.is_(True)).order_by(Place.name)).all()
    qs = list(item.questions)
    qs.sort(key=lambda x: x.position)
    return request.app.state.render(
        request,
        "items/edit.html",
        {
            "item": item,
            "categories": cats,
            "places": places,
            "current_user": user,
            "q1": qs[0].question if len(qs) > 0 else "",
            "a1": qs[0].answer if len(qs) > 0 else "",
            "q2": qs[1].question if len(qs) > 1 else "",
            "a2": qs[1].answer if len(qs) > 1 else "",
            "q3": qs[2].question if len(qs) > 2 else "",
            "a3": qs[2].answer if len(qs) > 2 else "",
        },
    )


@router.post("/items/{item_id}/edit")
async def edit_item(
    request: Request,
    item_id: int,
    description: str = Form(""),
    handover_note: str = Form(""),
    date_found: str = Form(""),
    q1: str = Form(""),
    a1: str = Form(""),
    q2: str = Form(""),
    a2: str = Form(""),
    q3: str = Form(""),
    a3: str = Form(""),
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    item = session.get(FoundItem, item_id)
    if item is None:
        raise HTTPException(404, "item not found")
    try:
        d = date.fromisoformat(date_found) if date_found else None
        item_svc.update_item(
            session,
            item=item,
            by=user,
            description=description,
            handover_note=handover_note,
            date_found=d,
            questions=[q1, q2, q3],
            answers=[a1, a2, a3],
        )
    except item_svc.ItemError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url=f"/items/{item.id}", status_code=302)


@router.post("/items/{item_id}/withdraw")
async def withdraw_item(
    request: Request,
    item_id: int,
    user: User = Depends(require_member),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    item = session.get(FoundItem, item_id)
    if item is None:
        raise HTTPException(404, "item not found")
    try:
        item_svc.withdraw_item(session, item=item, by=user)
    except item_svc.ItemError as e:
        raise HTTPException(400, str(e))
    # Photos for withdrawn posts are removed (F4.5).
    from app.photos.service import delete_photos_for_item

    delete_photos_for_item(session, item)
    return RedirectResponse(url="/items", status_code=302)
