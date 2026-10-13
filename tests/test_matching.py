"""Matching tests — covers F8."""
from __future__ import annotations

from datetime import date, timedelta

from app.auth import service as auth_svc
from app.db import session_scope
from app.items import service as item_svc
from app.lost import service as lost_svc
from app.matching.suggest import score_match, suggest_for_item, suggest_for_lost_report
from app.models.category import Category
from app.models.lost_report import LostReport
from app.models.place import Place
from app.models.user import AccountStatus, User


def _user(mobile):
    with session_scope() as s:
        u = auth_svc.signup(
            s, full_name="X", department="CSE", batch_or_session="2024",
            mobile=mobile, password="password123",
            is_member_confirmed=True, is_adult_confirmed=True,
        )
        u.status = AccountStatus.APPROVED
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


def test_score_match_requires_same_category():
    score, _, _, _ = score_match(
        category_a=1, category_b=2, place_a=1, place_b=1,
        date_a=date(2026, 1, 1), date_b=date(2026, 1, 2),
        description_a="bottle", description_b="bottle",
    )
    assert score == 0


def test_score_match_same_place_bonus():
    score, shared, same_place, _ = score_match(
        category_a=1, category_b=1, place_a=1, place_b=1,
        date_a=date(2026, 1, 1), date_b=date(2026, 1, 2),
        description_a="black water bottle", description_b="black bottle",
    )
    assert same_place is True
    assert {"black", "bottle"} <= set(shared)


def test_score_match_keyword_only():
    score, shared, same_place, _ = score_match(
        category_a=1, category_b=1, place_a=1, place_b=2,
        date_a=date(2026, 1, 1), date_b=date(2026, 1, 1),
        description_a="red scarf", description_b="red scarf",
    )
    assert same_place is False
    # +2 for two shared keywords (red, scarf)
    assert score >= 2


def test_score_match_date_close_bonus():
    score_close, _, _, _ = score_match(
        category_a=1, category_b=1, place_a=1, place_b=2,
        date_a=date(2026, 1, 1), date_b=date(2026, 1, 3),
        description_a="x", description_b="y",
    )
    score_far, _, _, _ = score_match(
        category_a=1, category_b=1, place_a=1, place_b=2,
        date_a=date(2026, 1, 1), date_b=date(2026, 1, 8),
        description_a="x", description_b="y",
    )
    assert score_close > score_far


def test_suggest_for_lost_report_finds_match():
    u = _user("+8801711111111")
    today = date.today()
    with session_scope() as s:
        c = Category(name="Electronics", sensitive=False, is_active=True)
        p1 = Place(name="Library", is_active=True)
        p2 = Place(name="Cafeteria", is_active=True)
        s.add(c)
        s.add(p1)
        s.add(p2)
        s.commit()
        s.refresh(c)
        s.refresh(p1)
        s.refresh(p2)
        u2 = s.get(User, u.id)
        item = item_svc.create_item(
            s, finder=u2, category_id=c.id, place_id=p1.id,
            date_found=today, description="black laptop bag",
            handover_note="", custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        report = lost_svc.create_lost_report(
            session=s, owner=u2, category_id=c.id, place_id=p1.id,
            date_lost=today - timedelta(days=1),
            description="black laptop bag with charger",
        )
    with session_scope() as s:
        matches = suggest_for_lost_report(s, report, u2)
        assert any(m.other_id == item.id for m in matches)


def test_suggest_for_lost_report_filters_by_category():
    u = _user("+8801722222222")
    today = date.today()
    with session_scope() as s:
        c1 = Category(name="Bottle", sensitive=False, is_active=True)
        c2 = Category(name="Book", sensitive=False, is_active=True)
        p1 = Place(name="Library", is_active=True)
        s.add(c1)
        s.add(c2)
        s.add(p1)
        s.commit()
        s.refresh(c1)
        s.refresh(c2)
        s.refresh(p1)
        u2 = s.get(User, u.id)
        # An item in a different category should never match.
        item_svc.create_item(
            s, finder=u2, category_id=c2.id, place_id=p1.id,
            date_found=today, description="x",
            handover_note="", custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        report = lost_svc.create_lost_report(
            session=s, owner=u2, category_id=c1.id, place_id=p1.id,
            date_lost=today, description="x",
        )
    with session_scope() as s:
        matches = suggest_for_lost_report(s, report, u2)
        assert matches == []


def test_suggest_for_item_finds_match():
    u = _user("+8801733333333")
    today = date.today()
    with session_scope() as s:
        c = Category(name="C", sensitive=False, is_active=True)
        p = Place(name="P", is_active=True)
        s.add(c)
        s.add(p)
        s.commit()
        s.refresh(c)
        s.refresh(p)
        u2 = s.get(User, u.id)
        item = item_svc.create_item(
            s, finder=u2, category_id=c.id, place_id=p.id,
            date_found=today, description="silver pen",
            handover_note="", custody_requested="finder",
            questions=["q"], answers=["a"],
        )
        lost_svc.create_lost_report(
            session=s, owner=u2, category_id=c.id, place_id=p.id,
            date_lost=today, description="silver pen",
        )
    with session_scope() as s:
        item2 = s.get(__import__("app.models.item", fromlist=["FoundItem"]).FoundItem, item.id)
        matches = suggest_for_item(s, item2, u2)
        assert len(matches) >= 1
