"""Photo serving route.

Bytes never leak to logged-out, pending or suspended users. Only
approved members can load an image. Returns ``image/webp`` (or
``image/jpeg`` fallback) with private cache headers.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import Response as FastResponse
from sqlmodel import Session, select

from app.db import get_session
from app.deps import get_current_user_optional
from app.models.photo import Photo
from app.models.user import User

router = APIRouter()


@router.get("/photos/{photo_id}")
def serve_photo(
    request: Request,
    photo_id: int,
    session: Session = Depends(get_session),
    user: User | None = Depends(get_current_user_optional),
):
    if user is None or user.status.value != "approved":
        # Don't leak existence.
        raise HTTPException(404, "not found")

    photo = session.exec(select(Photo).where(Photo.id == photo_id)).one_or_none()
    if photo is None:
        raise HTTPException(404, "not found")

    headers = {
        "Cache-Control": "private, max-age=0, no-cache",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline",
    }
    return FastResponse(content=photo.bytes_, media_type=photo.mime_type, headers=headers)
