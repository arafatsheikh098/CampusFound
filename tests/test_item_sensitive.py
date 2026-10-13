"""Sensitive category forces custody=office and ignores photo bytes."""
from __future__ import annotations

from datetime import date

from app.auth import service as auth_svc
from app.db import session_scope
from app.items import service as item_svc
from app.models.category import Category
from app.models.item import Custody
from app.models.place import Place
from app.models.user import AccountStatus, User


def _seed(mobile="+8801712345678"):
    with session_scope() as s:
        u = auth_svc.signup(
            s,
            full_name="X",
            department="CSE",
            batch_or_session="2024",
            mobile=mobile,
            password="password123",
            is_member_confirmed=True,
            is_adult_confirmed=True,
        )
        u.status = AccountStatus.APPROVED
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


def test_sensitive_category_forces_office_custody():
    u = _seed()
    with session_scope() as s:
        s.add(Place(name="Library", is_active=True))
        s.add(Category(name="ID card", sensitive=True, is_active=True))
        s.add(Category(name="Phone", sensitive=False, is_active=True))
        s.commit()
        place = s.exec(__import__("sqlmodel").select(Place)).one()
        sensitive = next(c for c in s.exec(__import__("sqlmodel").select(Category)).all() if c.sensitive)
        user = s.get(User, u.id)
        item = item_svc.create_item(
            s,
            finder=user,
            category_id=sensitive.id,
            place_id=place.id,
            date_found=date.today(),
            description="some id card",
            handover_note="hand to office",
            custody_requested="finder",  # tampered input: client says finder
            questions=["What is the ID number?"],
            answers=["12345"],
            has_photo=True,  # tampered input: client sends a photo
        )
    assert item.custody == Custody.OFFICE
    # has_photo was ignored, so no Photo row
    from app.models.photo import Photo

    with session_scope() as s:
        photos = s.exec(__import__("sqlmodel").select(Photo).where(Photo.item_id == item.id)).all()
        assert photos == []
