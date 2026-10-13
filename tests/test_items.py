"""Found-item creation tests."""
from __future__ import annotations

from datetime import date, timedelta

from freezegun import freeze_time

from app.auth import service as auth_svc
from app.db import session_scope
from app.items import service as item_svc
from app.models.category import Category
from app.models.item import Custody, FoundItem
from app.models.place import Place
from app.models.user import AccountStatus


def _make_user(mobile="+8801712345678", approved=True, moderator=False):
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
        u.is_moderator = moderator
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


def _make_place(name="Library"):
    with session_scope() as s:
        p = Place(name=name, is_active=True)
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


def _make_category(name="Electronics", sensitive=False):
    with session_scope() as s:
        c = Category(name=name, sensitive=sensitive, is_active=True)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c.id


def test_create_item_basic():
    u = _make_user()
    pid = _make_place()
    cid = _make_category()
    with session_scope() as s:
        u2 = s.get(__import__("app.models.user", fromlist=["User"]).User, u.id)
        item = item_svc.create_item(
            s,
            finder=u2,
            category_id=cid,
            place_id=pid,
            date_found=date.today() - timedelta(days=5),
            description="A black bottle",
            handover_note="Library desk 10-13",
            custody_requested="finder",
            questions=["What is your name?"],
            answers=["Alice"],
        )
        assert item.id is not None
        assert item.status.value == "open"
        assert item.custody == Custody.FINDER
        assert len(item.questions) == 1
        assert item.questions[0].answer == "Alice"


def test_date_found_in_future_rejected():
    u = _make_user()
    pid = _make_place()
    cid = _make_category()
    with session_scope() as s:
        u2 = s.get(__import__("app.models.user", fromlist=["User"]).User, u.id)
        import pytest
        with pytest.raises(item_svc.ItemError):
            item_svc.create_item(
                s,
                finder=u2,
                category_id=cid,
                place_id=pid,
                date_found=date.today() + timedelta(days=1),
                description="x",
                handover_note="",
                custody_requested="finder",
                questions=["q"],
                answers=["a"],
            )


def test_date_found_too_old_rejected():
    u = _make_user()
    pid = _make_place()
    cid = _make_category()
    with session_scope() as s:
        u2 = s.get(__import__("app.models.user", fromlist=["User"]).User, u.id)
        import pytest
        with pytest.raises(item_svc.ItemError):
            item_svc.create_item(
                s,
                finder=u2,
                category_id=cid,
                place_id=pid,
                date_found=date.today() - timedelta(days=61),
                description="x",
                handover_note="",
                custody_requested="finder",
                questions=["q"],
                answers=["a"],
            )


def test_date_found_at_exactly_60_days_accepted():
    u = _make_user()
    pid = _make_place()
    cid = _make_category()
    today = date.today()
    with freeze_time(today):
        with session_scope() as s:
            u2 = s.get(__import__("app.models.user", fromlist=["User"]).User, u.id)
            item = item_svc.create_item(
                s,
                finder=u2,
                category_id=cid,
                place_id=pid,
                date_found=today - timedelta(days=59),  # 59 days ago
                description="x",
                handover_note="",
                custody_requested="finder",
                questions=["q"],
                answers=["a"],
            )
            assert item.id is not None


def test_description_over_300_rejected():
    u = _make_user()
    pid = _make_place()
    cid = _make_category()
    with session_scope() as s:
        u2 = s.get(__import__("app.models.user", fromlist=["User"]).User, u.id)
        import pytest
        with pytest.raises(item_svc.ItemError):
            item_svc.create_item(
                s,
                finder=u2,
                category_id=cid,
                place_id=pid,
                date_found=date.today(),
                description="x" * 301,
                handover_note="",
                custody_requested="finder",
                questions=["q"],
                answers=["a"],
            )


def test_questions_count_limits():
    u = _make_user()
    pid = _make_place()
    cid = _make_category()
    with session_scope() as s:
        u2 = s.get(__import__("app.models.user", fromlist=["User"]).User, u.id)
        import pytest
        with pytest.raises(item_svc.ItemError):
            item_svc.create_item(
                s,
                finder=u2,
                category_id=cid,
                place_id=pid,
                date_found=date.today(),
                description="x",
                handover_note="",
                custody_requested="finder",
                questions=[],
                answers=[],
            )
        with pytest.raises(item_svc.ItemError):
            item_svc.create_item(
                s,
                finder=u2,
                category_id=cid,
                place_id=pid,
                date_found=date.today(),
                description="x",
                handover_note="",
                custody_requested="finder",
                questions=["q1", "q2", "q3", "q4"],
                answers=["a1", "a2", "a3", "a4"],
            )


def test_handover_note_over_150_rejected():
    u = _make_user()
    pid = _make_place()
    cid = _make_category()
    with session_scope() as s:
        u2 = s.get(__import__("app.models.user", fromlist=["User"]).User, u.id)
        import pytest
        with pytest.raises(item_svc.ItemError):
            item_svc.create_item(
                s,
                finder=u2,
                category_id=cid,
                place_id=pid,
                date_found=date.today(),
                description="x",
                handover_note="x" * 151,
                custody_requested="finder",
                questions=["q"],
                answers=["a"],
            )


def test_only_owner_or_moderator_can_edit():
    u1 = _make_user(mobile="+8801712345678")
    u2 = _make_user(mobile="+8801722222222")
    pid = _make_place()
    cid = _make_category()
    with session_scope() as s:
        from app.models.user import User

        u1b = s.get(User, u1.id)
        item = item_svc.create_item(
            s,
            finder=u1b,
            category_id=cid,
            place_id=pid,
            date_found=date.today(),
            description="x",
            handover_note="",
            custody_requested="finder",
            questions=["q"],
            answers=["a"],
        )
    with session_scope() as s:
        item2 = s.get(FoundItem, item.id)
        u2b = s.get(User, u2.id)
        import pytest
        with pytest.raises(item_svc.ItemError):
            item_svc.update_item(
                s, item=item2, by=u2b, description="hijack"
            )
    with session_scope() as s:
        item3 = s.get(FoundItem, item.id)
        u1c = s.get(User, u1.id)
        item_svc.update_item(
            s, item=item3, by=u1c, description="ok update"
        )
    with session_scope() as s:
        item4 = s.get(FoundItem, item.id)
        assert item4.description == "ok update"


def test_withdraw_only_owner_or_moderator():
    u1 = _make_user(mobile="+8801712345678")
    u2 = _make_user(mobile="+8801722222222")
    pid = _make_place()
    cid = _make_category()
    with session_scope() as s:
        from app.models.user import User

        u1b = s.get(User, u1.id)
        item = item_svc.create_item(
            s,
            finder=u1b,
            category_id=cid,
            place_id=pid,
            date_found=date.today(),
            description="x",
            handover_note="",
            custody_requested="finder",
            questions=["q"],
            answers=["a"],
        )
    with session_scope() as s:
        from app.models.user import User

        item2 = s.get(FoundItem, item.id)
        u2b = s.get(User, u2.id)
        import pytest
        with pytest.raises(item_svc.ItemError):
            item_svc.withdraw_item(s, item=item2, by=u2b)
