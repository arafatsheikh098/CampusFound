"""Moderation service: approve, reject, suspend, hide, restore, delete."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from app.audit import write_audit
from app.models.item import FoundItem, ItemStatus
from app.models.report import Report, ReportTarget
from app.models.user import AccountStatus, User


class ModError(ValueError):
    pass


def set_account_status(
    session: Session,
    *,
    user: User,
    new_status: AccountStatus,
    by: User,
) -> User:
    if not by.is_moderator:
        raise ModError("only moderators can change account status")
    if user.id == by.id:
        raise ModError("you cannot change your own status")
    user.status = new_status
    if new_status == AccountStatus.SUSPENDED:
        user.suspended_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    write_audit(
        session,
        actor_id=by.id,
        actor_label=by.full_name,
        action="account_status_changed",
        target_kind="user",
        target_id=user.id,
        extra={"new_status": new_status.value},
    )
    session.commit()
    return user


def hide_item(session: Session, *, item: FoundItem, by: User) -> FoundItem:
    if not by.is_moderator:
        raise ModError("only moderators can hide posts")
    item.hidden = True
    session.add(item)
    session.commit()
    session.refresh(item)
    write_audit(
        session,
        actor_id=by.id,
        actor_label=by.full_name,
        action="item_hidden",
        target_kind="found_item",
        target_id=item.id,
    )
    session.commit()
    return item


def restore_item(session: Session, *, item: FoundItem, by: User) -> FoundItem:
    if not by.is_moderator:
        raise ModError("only moderators can restore posts")
    item.hidden = False
    session.add(item)
    session.commit()
    session.refresh(item)
    write_audit(
        session,
        actor_id=by.id,
        actor_label=by.full_name,
        action="item_restored",
        target_kind="found_item",
        target_id=item.id,
    )
    session.commit()
    return item


def file_report(
    session: Session,
    *,
    by: User,
    target_kind: ReportTarget,
    target_id: int,
    reason: str,
) -> Report:
    reason = (reason or "").strip()[:300]
    if not reason:
        raise ModError("reason is required")
    r = Report(
        reporter_id=by.id,
        target_kind=target_kind,
        target_id=target_id,
        reason=reason,
    )
    session.add(r)
    session.commit()
    session.refresh(r)
    write_audit(
        session,
        actor_id=by.id,
        actor_label=by.full_name,
        action="report_filed",
        target_kind=target_kind.value,
        target_id=target_id,
        extra={"reason": reason},
    )
    session.commit()
    return r
