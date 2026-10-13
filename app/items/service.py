"""Found-item service: validation, creation, update, withdraw."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import and_, or_
from sqlmodel import Session, select

from app.audit import write_audit
from app.config import get_settings
from app.models.category import Category
from app.models.item import Custody, FoundItem, ItemStatus, VerificationQuestion
from app.models.place import Place
from app.models.user import User

# Field limits from SCOPE
DESCRIPTION_MAX = 300
HANDOVER_NOTE_MAX = 150
QUESTION_MAX = 120
ANSWER_MAX = 120
QUESTIONS_MIN = 1
QUESTIONS_MAX = 3


class ItemError(ValueError):
    pass


def _validate_date_found(d: date) -> None:
    today = date.today()
    if d > today:
        raise ItemError("date_found cannot be in the future")
    max_days = get_settings().days_date_found_max
    if (today - d).days > max_days:
        raise ItemError(f"date_found cannot be older than {max_days} days")


def _validate_text(name: str, value: str, max_len: int) -> str:
    value = (value or "").strip()
    if len(value) > max_len:
        raise ItemError(f"{name} is at most {max_len} characters")
    return value


def _questions_payload(questions: List[str], answers: List[str]) -> List[Tuple[str, str]]:
    qs = [q for q in (questions or []) if (q or "").strip()]
    # Filter answers the same way so a partially-filled form doesn't
    # produce a "must match" error. Empty trailing slots from the
    # HTML form are discarded.
    ans = [a for a in (answers or []) if (a or "").strip()]
    if not (QUESTIONS_MIN <= len(qs) <= QUESTIONS_MAX):
        raise ItemError(f"between {QUESTIONS_MIN} and {QUESTIONS_MAX} questions are required")
    if len(qs) != len(ans):
        raise ItemError("number of answers must match number of questions")
    out = []
    for i, (q, a) in enumerate(zip(qs, ans), start=1):
        out.append((_validate_text("question", q, QUESTION_MAX), _validate_text("answer", a, ANSWER_MAX)))
    return out


def _enforce_sensitive(category: Category, requested_custody: str, has_photo: bool) -> Custody:
    """Sensitive categories force custody=office and never allow photos."""
    if category.sensitive:
        return Custody.OFFICE
    try:
        return Custody(requested_custody)
    except ValueError:
        return Custody.FINDER


def create_item(
    session: Session,
    *,
    finder: User,
    category_id: int,
    place_id: int,
    date_found: date,
    description: str,
    handover_note: str,
    custody_requested: str,
    questions: List[str],
    answers: List[str],
    has_photo: bool = False,
) -> FoundItem:
    category = session.get(Category, category_id)
    if category is None or not category.is_active:
        raise ItemError("category not found or inactive")
    place = session.get(Place, place_id)
    if place is None or not place.is_active:
        raise ItemError("place not found or inactive")
    _validate_date_found(date_found)
    description = _validate_text("description", description, DESCRIPTION_MAX)
    handover_note = _validate_text("handover_note", handover_note, HANDOVER_NOTE_MAX)
    custody = _enforce_sensitive(category, custody_requested, has_photo)
    if category.sensitive and has_photo:
        has_photo = False  # server-side drop
    qa = _questions_payload(questions, answers)

    item = FoundItem(
        finder_id=finder.id,
        category_id=category_id,
        place_id=place_id,
        date_found=date_found,
        description=description,
        handover_note=handover_note,
        custody=custody,
        status=ItemStatus.OPEN,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    for pos, (q, a) in enumerate(qa, start=1):
        session.add(
            VerificationQuestion(
                item_id=item.id,
                position=pos,
                question=q,
                answer=a,
            )
        )
    session.commit()
    write_audit(
        session,
        actor_id=finder.id,
        actor_label=finder.full_name,
        action="item_created",
        target_kind="found_item",
        target_id=item.id,
    )
    session.commit()
    return item


def update_item(
    session: Session,
    *,
    item: FoundItem,
    by: User,
    description: Optional[str] = None,
    handover_note: Optional[str] = None,
    date_found: Optional[date] = None,
    questions: Optional[List[str]] = None,
    answers: Optional[List[str]] = None,
) -> FoundItem:
    if not (item.finder_id == by.id or by.is_moderator):
        raise ItemError("only the finder or a moderator can edit this post")
    if item.status in (ItemStatus.RETURNED, ItemStatus.WITHDRAWN, ItemStatus.UNCLAIMED):
        raise ItemError("item is no longer editable")
    if date_found is not None:
        _validate_date_found(date_found)
        item.date_found = date_found
    if description is not None:
        item.description = _validate_text("description", description, DESCRIPTION_MAX)
    if handover_note is not None:
        item.handover_note = _validate_text("handover_note", handover_note, HANDOVER_NOTE_MAX)
    if questions is not None or answers is not None:
        # Replace all questions
        existing = session.exec(
            select(VerificationQuestion).where(VerificationQuestion.item_id == item.id)
        ).all()
        for q in existing:
            session.delete(q)
        session.commit()
        qa = _questions_payload(questions or [], answers or [])
        for pos, (q, a) in enumerate(qa, start=1):
            session.add(VerificationQuestion(item_id=item.id, position=pos, question=q, answer=a))
    item.updated_at = datetime.utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    write_audit(
        session,
        actor_id=by.id,
        actor_label=by.full_name,
        action="item_updated",
        target_kind="found_item",
        target_id=item.id,
    )
    session.commit()
    return item


def withdraw_item(session: Session, *, item: FoundItem, by: User) -> FoundItem:
    if not (item.finder_id == by.id or by.is_moderator):
        raise ItemError("only the finder or a moderator can withdraw this post")
    if item.status in (ItemStatus.RETURNED, ItemStatus.WITHDRAWN):
        raise ItemError("already withdrawn or returned")
    item.status = ItemStatus.WITHDRAWN
    item.withdrawn_at = datetime.utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    # Drop photos per F4.5: photos for withdrawn posts are deleted.
    from app.photos.service import delete_photos_for_item

    delete_photos_for_item(session, item)
    write_audit(
        session,
        actor_id=by.id,
        actor_label=by.full_name,
        action="item_withdrawn",
        target_kind="found_item",
        target_id=item.id,
    )
    session.commit()
    return item


def item_visible_to(item: FoundItem, user: Optional[User]) -> bool:
    """Items are visible to anyone who is logged in as approved (M5)."""
    if user is None:
        return False
    return user.status.value == "approved"


def sweep_unclaimed(session: Session) -> int:
    """Mark items older than ``days_date_found_max`` without a claim as
    UNCLAIMED. Returns the number of items moved.
    """
    cutoff = date.today() - timedelta(days=get_settings().days_date_found_max)
    rows = session.exec(
        select(FoundItem).where(
            FoundItem.status == ItemStatus.OPEN,
            FoundItem.date_found < cutoff,
        )
    ).all()
    count = 0
    for r in rows:
        r.status = ItemStatus.UNCLAIMED
        r.unclaimed_at = datetime.utcnow()
        session.add(r)
        count += 1
    session.commit()
    return count
