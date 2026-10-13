"""DB-using matching helpers.

The pure scoring logic lives in :mod:`app.matching.score` (no DB / web
imports). This module wraps it with SQLAlchemy session queries to
fetch candidates and return ranked matches.
"""
from __future__ import annotations

from typing import List, Optional

from sqlmodel import Session, select

from app.matching.score import Match, score_match
from app.models.item import FoundItem, ItemStatus
from app.models.lost_report import LostReport
from app.models.user import User


def suggest_for_item(
    session: Session,
    item: FoundItem,
    user: Optional[User] = None,
    *,
    min_score: int = 1,
    limit: int = 5,
) -> List[Match]:
    """Return ranked lost-report matches for a found item."""
    rows = session.exec(
        select(LostReport).where(
            LostReport.is_open.is_(True),
            LostReport.category_id == item.category_id,
        )
    ).all()
    out: List[Match] = []
    for r in rows:
        score, shared, same_place, days = score_match(
            category_a=item.category_id,
            category_b=r.category_id,
            place_a=item.place_id,
            place_b=r.place_id,
            date_a=item.date_found,
            date_b=r.date_lost,
            description_a=item.description,
            description_b=r.description,
        )
        if score >= min_score:
            out.append(
                Match(
                    other_id=r.id,
                    score=score,
                    shared_keywords=shared,
                    same_place=same_place,
                    days_apart=days,
                )
            )
    out.sort(key=lambda m: (-m.score, m.other_id))
    return out[:limit]


def suggest_for_lost_report(
    session: Session,
    report: LostReport,
    user: Optional[User] = None,
    *,
    min_score: int = 1,
    limit: int = 5,
) -> List[Match]:
    """Return ranked found-item matches for a lost report."""
    rows = session.exec(
        select(FoundItem).where(
            FoundItem.status == ItemStatus.OPEN,
            FoundItem.hidden.is_(False),
            FoundItem.category_id == report.category_id,
        )
    ).all()
    out: List[Match] = []
    for it in rows:
        score, shared, same_place, days = score_match(
            category_a=report.category_id,
            category_b=it.category_id,
            place_a=report.place_id,
            place_b=it.place_id,
            date_a=report.date_lost,
            date_b=it.date_found,
            description_a=report.description,
            description_b=it.description,
        )
        if score >= min_score:
            out.append(
                Match(
                    other_id=it.id,
                    score=score,
                    shared_keywords=shared,
                    same_place=same_place,
                    days_apart=days,
                )
            )
    out.sort(key=lambda m: (-m.score, m.other_id))
    return out[:limit]
