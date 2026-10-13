"""Lost report service: create, update, withdraw, mark found."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Session, select

from app.audit import write_audit
from app.models.category import Category
from app.models.lost_report import LostReport
from app.models.place import Place
from app.models.user import User

DESCRIPTION_MAX = 300
PRIVATE_NOTE_MAX = 300
DATE_LOST_MAX_DAYS = 60  # matches items


class LostReportError(ValueError):
    pass


def _validate_text(name: str, value: str, max_len: int) -> str:
    value = (value or "").strip()
    if len(value) > max_len:
        raise LostReportError(f"{name} is at most {max_len} characters")
    return value


def create_lost_report(
    session: Session,
    *,
    owner: User,
    category_id: int,
    place_id: int,
    date_lost: date,
    description: str,
    private_note: str = "",
) -> LostReport:
    if owner.status.value != "approved":
        raise LostReportError("only approved members can file a lost report")
    cat = session.get(Category, category_id)
    if cat is None or not cat.is_active:
        raise LostReportError("category not found or inactive")
    place = session.get(Place, place_id)
    if place is None or not place.is_active:
        raise LostReportError("place not found or inactive")
    if date_lost > date.today():
        raise LostReportError("date_lost cannot be in the future")
    if (date.today() - date_lost).days > DATE_LOST_MAX_DAYS:
        raise LostReportError(f"date_lost cannot be older than {DATE_LOST_MAX_DAYS} days")
    description = _validate_text("description", description, DESCRIPTION_MAX)
    private_note = _validate_text("private_note", private_note, PRIVATE_NOTE_MAX)
    report = LostReport(
        owner_id=owner.id,
        category_id=category_id,
        place_id=place_id,
        date_lost=date_lost,
        description=description,
        private_note=private_note,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    write_audit(
        session,
        actor_id=owner.id,
        actor_label=owner.full_name,
        action="lost_report_created",
        target_kind="lost_report",
        target_id=report.id,
    )
    session.commit()
    return report


def withdraw_lost_report(session: Session, *, report: LostReport, by: User) -> LostReport:
    if report.owner_id != by.id and not by.is_moderator:
        raise LostReportError("only the owner or a moderator can withdraw this report")
    if not report.is_open:
        raise LostReportError("already closed")
    report.is_open = False
    session.add(report)
    session.commit()
    session.refresh(report)
    write_audit(
        session,
        actor_id=by.id,
        actor_label=by.full_name,
        action="lost_report_withdrawn",
        target_kind="lost_report",
        target_id=report.id,
    )
    session.commit()
    return report


def mark_found(session: Session, *, report: LostReport, by: User) -> LostReport:
    if report.owner_id != by.id and not by.is_moderator:
        raise LostReportError("only the owner or a moderator can mark this report found")
    report.is_open = False
    session.add(report)
    session.commit()
    session.refresh(report)
    write_audit(
        session,
        actor_id=by.id,
        actor_label=by.full_name,
        action="lost_report_marked_found",
        target_kind="lost_report",
        target_id=report.id,
    )
    session.commit()
    return report
