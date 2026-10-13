"""Photo persistence helpers.

Wraps :mod:`app.photos.processing` for item-post attachment, and
centralises the rules around how many photos an item can have and
how they are removed (withdraw, return, sensitive categories).
"""
from __future__ import annotations

from typing import Iterable, List

from sqlmodel import Session, select

from app.audit import write_audit
from app.models.category import Category
from app.models.item import FoundItem
from app.models.photo import Photo
from app.models.user import User
from app.photos.processing import (
    MAX_PHOTOS_PER_ITEM,
    PhotoError,
    process_image_bytes,
)


def attach_photos(
    session: Session,
    *,
    item: FoundItem,
    uploads: Iterable[tuple[bytes, str]],
    by: User,
) -> List[Photo]:
    """Validate and attach photos to ``item``.

    ``uploads`` is an iterable of ``(bytes, filename)``. Sensitive
    categories never accept photos; the bytes are dropped silently.
    """
    category = session.get(Category, item.category_id)
    if category is not None and category.sensitive:
        return []

    existing = session.exec(select(Photo).where(Photo.item_id == item.id)).all()
    if len(existing) >= MAX_PHOTOS_PER_ITEM:
        raise PhotoError(f"at most {MAX_PHOTOS_PER_ITEM} photos per post")

    attached: List[Photo] = []
    for data, _name in uploads:
        if not data:
            continue
        if len(existing) + len(attached) >= MAX_PHOTOS_PER_ITEM:
            break
        proc = process_image_bytes(data)
        p = Photo(
            item_id=item.id,
            mime_type=proc.mime_type,
            width=proc.width,
            height=proc.height,
            bytes_=proc.bytes_,
            sha256=proc.sha256,
        )
        session.add(p)
        attached.append(p)
    if attached:
        session.commit()
        write_audit(
            session,
            actor_id=by.id,
            actor_label=by.full_name,
            action="photos_attached",
            target_kind="found_item",
            target_id=item.id,
            extra={"count": len(attached)},
        )
        session.commit()
    return attached


def delete_photos_for_item(session: Session, item: FoundItem) -> int:
    """Delete every photo attached to ``item``. Returns the count."""
    rows = session.exec(select(Photo).where(Photo.item_id == item.id)).all()
    n = 0
    for r in rows:
        session.delete(r)
        n += 1
    if n:
        session.commit()
    return n
