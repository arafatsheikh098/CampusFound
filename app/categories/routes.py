"""Categories — moderator-managed, with a `sensitive` flag.

The ``sensitive`` flag is only togglable by moderators through this
endpoint. Non-moderator routes cannot edit it.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.deps import check_csrf, get_current_user_optional, require_moderator
from app.models.category import Category
from app.models.user import User

router = APIRouter()


@router.get("/categories", response_class=HTMLResponse)
def list_categories(
    request: Request,
    session: Session = Depends(get_session),
    user: User | None = Depends(get_current_user_optional),
):
    cats = session.exec(select(Category).order_by(Category.name)).all()
    return request.app.state.render(
        request,
        "categories/list.html",
        {
            "categories": cats,
            "current_user": user,
            "is_moderator": bool(user and user.is_moderator and user.status.value == "approved"),
        },
    )


@router.post("/categories", dependencies=[Depends(require_moderator)])
async def create_category(
    request: Request,
    name: str = Form(...),
    sensitive: str = Form(""),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    name = name.strip()[:120]
    if not name:
        raise HTTPException(400, "name is required")
    existing = session.exec(select(Category).where(Category.name == name)).one_or_none()
    if existing is not None:
        raise HTTPException(400, "category already exists")
    session.add(Category(name=name, sensitive=bool(sensitive), is_active=True))
    session.commit()
    return RedirectResponse(url="/categories", status_code=302)


@router.post("/categories/{category_id}/toggle-sensitive", dependencies=[Depends(require_moderator)])
async def toggle_sensitive(
    request: Request,
    category_id: int,
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    c = session.get(Category, category_id)
    if c is None:
        raise HTTPException(404, "category not found")
    c.sensitive = not c.sensitive
    session.add(c)
    session.commit()
    return RedirectResponse(url="/categories", status_code=302)


@router.post("/categories/{category_id}/delete", dependencies=[Depends(require_moderator)])
async def delete_category(
    request: Request,
    category_id: int,
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    c = session.get(Category, category_id)
    if c is None:
        raise HTTPException(404, "category not found")
    c.is_active = False
    session.add(c)
    session.commit()
    return RedirectResponse(url="/categories", status_code=302)
