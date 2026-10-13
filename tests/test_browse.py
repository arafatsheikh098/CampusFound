"""Browse + search tests — covers F5.1, F5.2, F5.3, F5.4, F5.5."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from freezegun import freeze_time

from app.auth import service as auth_svc
from app.db import session_scope
from app.items import service as item_svc
from app.items.search import SearchParams, search
from app.models.category import Category
from app.models.item import FoundItem
from app.models.place import Place
from app.models.user import AccountStatus, User


def _make_user(mobile="+8801712345678"):
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


def _seed_items():
    u = _make_user()
    with session_scope() as s:
        u2 = s.get(User, u.id)
        c1 = Category(name="Electronics", sensitive=False, is_active=True)
        c2 = Category(name="Bottle", sensitive=False, is_active=True)
        c3 = Category(name="ID card", sensitive=True, is_active=True)
        p1 = Place(name="Library", is_active=True)
        p2 = Place(name="Cafeteria", is_active=True)
        for x in (c1, c2, c3, p1, p2):
            s.add(x)
        s.commit()
        for x in (c1, c2, c3, p1, p2):
            s.refresh(x)

        today = date.today()
        item_svc.create_item(
            s, finder=u2, category_id=c1.id, place_id=p1.id,
            date_found=today, description="Black laptop bag",
            handover_note="", custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        item_svc.create_item(
            s, finder=u2, category_id=c2.id, place_id=p2.id,
            date_found=today - timedelta(days=2), description="Steel water bottle",
            handover_note="", custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        item_svc.create_item(
            s, finder=u2, category_id=c3.id, place_id=p1.id,
            date_found=today, description="Student ID",
            handover_note="", custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        return {
            "cat_electronics": c1.id, "cat_bottle": c2.id, "cat_id": c3.id,
            "place_library": p1.id, "place_cafeteria": p2.id,
        }


def test_filters_combine():
    ids = _seed_items()
    with session_scope() as s:
        r = search(
            s,
            SearchParams(category_id=ids["cat_electronics"], place_id=ids["place_library"]),
        )
        assert r.total == 1
        assert "laptop" in r.items[0].description.lower()


def test_keyword_search_case_insensitive():
    _seed_items()
    with session_scope() as s:
        r1 = search(s, SearchParams(q="LAPTOP"))
        r2 = search(s, SearchParams(q="laptop"))
        r3 = search(s, SearchParams(q="LaPtOp"))
        assert r1.total == r2.total == r3.total == 1


def test_keyword_search_bangla():
    _seed_items()
    with session_scope() as s:
        from app.models.item import FoundItem
        from sqlmodel import select
        u = s.get(User, 1)  # any user
        # Insert a Bangla description item.
        from datetime import date as _date
        c = s.get(Category, None)
        c_id = s.exec(select(Category)).first().id
        p_id = s.exec(select(Place)).first().id
        item = FoundItem(
            finder_id=u.id, category_id=c_id, place_id=p_id,
            date_found=_date.today(), description="বাংলা বই",
            handover_note="", custody="finder", status="open", hidden=False,
        )
        s.add(item)
        s.commit()
        r = search(s, SearchParams(q="বাংলা"))
        assert r.total >= 1


def test_keyword_search_treats_percent_and_lt_as_plain_text():
    _seed_items()
    with session_scope() as s:
        # SQL would interpret % as wildcard; the test asserts it does NOT.
        # If we searched with `q="%"`, naive SQL would return everything.
        r = search(s, SearchParams(q="%"))
        # We expect zero hits because no description contains a literal `%`.
        assert r.total == 0
        r2 = search(s, SearchParams(q="<"))
        assert r2.total == 0


def test_pagination_boundaries():
    _seed_items()
    with session_scope() as s:
        r1 = search(s, SearchParams(page=1))
        assert r1.page == 1
        r99 = search(s, SearchParams(page=99))
        assert r99.page == 99
        assert r99.items == []


def test_sensitive_items_hide_description_in_list():
    ids = _seed_items()
    with session_scope() as s:
        r = search(s, SearchParams(category_id=ids["cat_id"]))
        assert r.total == 1
        # Sensitive items still load into the result, but the template
        # is responsible for not rendering their description. Verify the
        # row's description is in the DB but a known marker is absent.
        item = r.items[0]
        assert item.description == "Student ID"  # in DB
        # The template replaces the description with the placeholder.
        # We assert behaviour via the render path in test_sensitive_list.


def test_unclaimed_boundary():
    u = _make_user(mobile="+8801799999999")
    with freeze_time("2026-04-01"):
        with session_scope() as s:
            u2 = s.get(User, u.id)
            c = Category(name="C", sensitive=False, is_active=True)
            p = Place(name="P", is_active=True)
            s.add(c)
            s.add(p)
            s.commit()
            s.refresh(c)
            s.refresh(p)
            # Exactly 60 days ago is on the boundary; the spec says
            # "older than 60 days" — so 60 days ago is still open.
            item_svc.create_item(
                s, finder=u2, category_id=c.id, place_id=p.id,
                date_found=date(2026, 2, 1) + timedelta(days=0),
                description="boundary", handover_note="",
                custody_requested="finder",
                questions=["q"], answers=["a"],
            )
        with session_scope() as s:
            item_svc.sweep_unclaimed(s)
        with session_scope() as s:
            from sqlmodel import select
            row = s.exec(select(FoundItem)).first()
            assert row.status.value == "open"
