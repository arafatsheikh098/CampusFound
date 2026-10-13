"""Places (campus locations) — moderator-managed.

Members can read the list to populate a dropdown; only moderators can
add, rename or delete a place.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.deps import check_csrf, get_current_user_optional, require_moderator
from app.models.place import Place
from app.models.user import User

router = APIRouter()


@router.get("/places", response_class=HTMLResponse)
def list_places(
    request: Request,
    session: Session = Depends(get_session),
    user: User | None = Depends(get_current_user_optional),
):
    places = session.exec(select(Place).order_by(Place.name)).all()
    return request.app.state.render(
        request,
        "places/list.html",
        {
            "places": places,
            "current_user": user,
            "is_moderator": bool(user and user.is_moderator and user.status.value == "approved"),
        },
    )


@router.post("/places", dependencies=[Depends(require_moderator)])
async def create_place(
    request: Request,
    name: str = Form(...),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    name = name.strip()[:120]
    if not name:
        raise HTTPException(400, "name is required")
    existing = session.exec(select(Place).where(Place.name == name)).one_or_none()
    if existing is not None:
        raise HTTPException(400, "place already exists")
    session.add(Place(name=name, is_active=True))
    session.commit()
    return RedirectResponse(url="/places", status_code=302)


@router.post("/places/{place_id}/rename", dependencies=[Depends(require_moderator)])
async def rename_place(
    request: Request,
    place_id: int,
    name: str = Form(...),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    p = session.get(Place, place_id)
    if p is None:
        raise HTTPException(404, "place not found")
    p.name = name.strip()[:120]
    session.add(p)
    session.commit()
    return RedirectResponse(url="/places", status_code=302)


@router.post("/places/{place_id}/delete", dependencies=[Depends(require_moderator)])
async def delete_place(
    request: Request,
    place_id: int,
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    p = session.get(Place, place_id)
    if p is None:
        raise HTTPException(404, "place not found")
    p.is_active = False  # soft delete
    session.add(p)
    session.commit()
    return RedirectResponse(url="/places", status_code=302)
