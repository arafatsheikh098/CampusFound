"""Photo pipeline tests — covers F4.1, F4.2, F4.6."""
from __future__ import annotations

import io
import os
import re
import struct
import zlib

import pytest
from PIL import Image

from app.auth import service as auth_svc
from app.db import session_scope
from app.models.category import Category
from app.models.item import FoundItem
from app.models.photo import Photo
from app.models.place import Place
from app.models.user import AccountStatus
from app.photos.processing import (
    PhotoError,
    process_image_bytes,
    synthesise_test_jpeg,
    synthesise_test_png,
)
from app.photos.service import attach_photos, delete_photos_for_item
from app.security import sign_session


def _make_user(mobile="+8801712345678", approved=True):
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


def _make_item(finder, sensitive=False, photos=()):
    with session_scope() as s:
        from app.models.user import User

        c = Category(name="TestCat" + str(sensitive), sensitive=sensitive, is_active=True)
        p = Place(name="Library", is_active=True)
        s.add(c)
        s.add(p)
        s.commit()
        s.refresh(c)
        s.refresh(p)

        from datetime import date

        u = s.get(User, finder.id)
        item = FoundItem(
            finder_id=u.id,
            category_id=c.id,
            place_id=p.id,
            date_found=date.today(),
            description="x",
            handover_note="",
        )
        s.add(item)
        s.commit()
        s.refresh(item)
        for data in photos:
            attach_photos(s, item=item, uploads=[(data, "a.png")], by=u)
        s.commit()
        return item.id


def test_jpeg_with_gps_is_stripped():
    raw = synthesise_test_jpeg(64, 64, exif_gps=True)
    out = process_image_bytes(raw)
    assert out.mime_type in ("image/webp", "image/jpeg")
    img = Image.open(io.BytesIO(out.bytes_))
    exif = img.getexif()
    assert not exif, "EXIF must be stripped"


def test_png_with_text_metadata_is_stripped():
    raw = synthesise_test_png(64, 64)
    out = process_image_bytes(raw)
    img = Image.open(io.BytesIO(out.bytes_))
    # No text chunks (PNG-only) and no EXIF (WebP) should survive.
    text = getattr(img, "text", {}) or {}
    assert text == {}
    assert not img.getexif()


def test_text_renamed_jpg_rejected():
    payload = b"this is plain text, not a real JPEG" * 20
    with pytest.raises(PhotoError):
        process_image_bytes(payload)


def test_truncated_jpeg_rejected():
    raw = synthesise_test_jpeg(32, 32, exif_gps=False)
    truncated = raw[: len(raw) // 2]
    with pytest.raises(PhotoError):
        process_image_bytes(truncated)


def test_oversize_rejected():
    raw = synthesise_test_png(64, 64) * 200_000  # way over 5MB
    with pytest.raises(PhotoError):
        process_image_bytes(raw)


def test_svg_rejected():
    svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>' * 10
    with pytest.raises(PhotoError):
        process_image_bytes(svg)


def test_polyglot_rejected():
    raw = synthesise_test_png(32, 32)
    # Append a script tag — must be detected and rejected.
    polyglot = raw + b"\n<script>alert(1)</script>"
    with pytest.raises(PhotoError):
        process_image_bytes(polyglot)


def test_empty_rejected():
    with pytest.raises(PhotoError):
        process_image_bytes(b"")


def test_long_side_capped_at_1024():
    raw = synthesise_test_jpeg(2400, 800, exif_gps=False)
    out = process_image_bytes(raw)
    img = Image.open(io.BytesIO(out.bytes_))
    assert max(img.width, img.height) <= 1024


def test_sensitive_category_drops_photos():
    u = _make_user()
    item_id = _make_item(u, sensitive=True, photos=[synthesise_test_png(64, 64)])
    with session_scope() as s:
        photos = s.exec(__import__("sqlmodel").select(Photo).where(Photo.item_id == item_id)).all()
        assert photos == []


def test_withdraw_deletes_photos():
    from app.items import service as item_svc

    u = _make_user()
    item_id = _make_item(u, photos=[synthesise_test_png(64, 64)])
    with session_scope() as s:
        item = s.get(FoundItem, item_id)
        u2 = s.get(__import__("app.models.user", fromlist=["User"]).User, u.id)
        item_svc.withdraw_item(s, item=item, by=u2)
    with session_scope() as s:
        photos = s.exec(__import__("sqlmodel").select(Photo).where(Photo.item_id == item_id)).all()
        assert photos == []


def test_attach_photos_respects_two_cap():
    u = _make_user()
    item_id = _make_item(u)
    with session_scope() as s:
        item = s.get(FoundItem, item_id)
        u2 = s.get(__import__("app.models.user", fromlist=["User"]).User, u.id)
        # 3 uploads but only 2 should be stored.
        attach_photos(
            s,
            item=item,
            uploads=[
                (synthesise_test_png(64, 64), "a.png"),
                (synthesise_test_png(64, 64), "b.png"),
                (synthesise_test_png(64, 64), "c.png"),
            ],
            by=u2,
        )
    with session_scope() as s:
        photos = s.exec(__import__("sqlmodel").select(Photo).where(Photo.item_id == item_id)).all()
        assert len(photos) == 2
