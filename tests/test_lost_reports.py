"""Lost report CRUD tests."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.auth import service as auth_svc
from app.db import session_scope
from app.lost import service as lost_svc
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


def _cat(s, name="C"):
    c = Category(name=name, sensitive=False, is_active=True)
    s.add(c)
    s.commit()
    s.refresh(c)
    return c


def _place(s, name="P"):
    p = Place(name=name, is_active=True)
    s.add(p)
    s.commit()
    s.refresh(p)
    return p


def test_create_lost_report_basic():
    u = _user("+8801711111111")
    with session_scope() as s:
        c = _cat(s)
        p = _place(s)
        u2 = s.get(User, u.id)
        r = lost_svc.create_lost_report(
            session=s, owner=u2, category_id=c.id, place_id=p.id,
            date_lost=date.today() - timedelta(days=1),
            description="red scarf",
            private_note="blue stripe",
        )
        assert r.id is not None
        assert r.is_open is True


def test_create_lost_report_future_date_rejected():
    u = _user("+8801722222222")
    with session_scope() as s:
        c = _cat(s)
        p = _place(s)
        u2 = s.get(User, u.id)
        with pytest.raises(lost_svc.LostReportError):
            lost_svc.create_lost_report(
                session=s, owner=u2, category_id=c.id, place_id=p.id,
                date_lost=date.today() + timedelta(days=1),
                description="x",
            )


def test_create_lost_report_too_old_rejected():
    u = _user("+8801733333333")
    with session_scope() as s:
        c = _cat(s)
        p = _place(s)
        u2 = s.get(User, u.id)
        with pytest.raises(lost_svc.LostReportError):
            lost_svc.create_lost_report(
                session=s, owner=u2, category_id=c.id, place_id=p.id,
                date_lost=date.today() - timedelta(days=120),
                description="x",
            )


def test_description_over_300_rejected():
    u = _user("+8801744444444")
    with session_scope() as s:
        c = _cat(s)
        p = _place(s)
        u2 = s.get(User, u.id)
        with pytest.raises(lost_svc.LostReportError):
            lost_svc.create_lost_report(
                session=s, owner=u2, category_id=c.id, place_id=p.id,
                date_lost=date.today(),
                description="x" * 301,
            )


def test_only_owner_or_moderator_can_withdraw():
    owner = _user("+8801755555551")
    other = _user("+8801755555552")
    with session_scope() as s:
        c = _cat(s)
        p = _place(s)
        u_o = s.get(User, owner.id)
        r = lost_svc.create_lost_report(
            session=s, owner=u_o, category_id=c.id, place_id=p.id,
            date_lost=date.today(), description="x",
        )
    with session_scope() as s:
        u_o2 = s.get(User, owner.id)
        u_t = s.get(User, other.id)
        report = s.get(LostReport, r.id)
        with pytest.raises(lost_svc.LostReportError):
            lost_svc.withdraw_lost_report(s, report=report, by=u_t)
        # Owner can withdraw.
        report = s.get(LostReport, r.id)
        lost_svc.withdraw_lost_report(s, report=report, by=u_o2)
