"""Pure matching between lost reports and found items.

The match score is computed in :func:`score_match` and is a pure
function over plain Python data — no DB, no I/O — so it can be unit
tested without a database. The :func:`suggest_for_item` and
:func:`suggest_for_lost_report` helpers wrap it with a SQLAlchemy
session to fetch candidates and return ranked matches.

Match formula (F8):
  - Same category is required.
  - +5 if the place matches.
  - +1 per shared keyword (intersection of the lowercased word sets,
    ignoring common stopwords).
  - +3 if the dates are within 3 days of each other.
  - +1 if within 7 days.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, List, Optional, Set, Tuple

from sqlmodel import Session, select

from app.models.item import FoundItem, ItemStatus
from app.models.lost_report import LostReport
from app.models.user import User

STOPWORDS: Set[str] = {
    "the", "a", "an", "is", "and", "or", "of", "to", "in", "on", "at",
    "with", "for", "by", "this", "that", "it", "i", "my", "your", "you",
    "একটি", "টি", "এই", "সেই", "আমার", "তোমার", "আমি",
}

_TOKEN_RE = re.compile(r"[\w\u0980-\u09FF]+", flags=re.UNICODE)


def _tokenize(text: str) -> Set[str]:
    if not text:
        return set()
    return {t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in STOPWORDS}


@dataclass
class Match:
    other_id: int  # id of the other side (item id or lost report id)
    score: int
    shared_keywords: List[str]
    same_place: bool
    days_apart: Optional[int]


def score_match(
    *,
    category_a: int,
    category_b: int,
    place_a: int,
    place_b: int,
    date_a: date,
    date_b: date,
    description_a: str,
    description_b: str,
) -> Tuple[int, List[str], bool, Optional[int]]:
    """Return ``(score, shared_keywords, same_place, days_apart)``.

    Same category is required; if not, the score is 0 and no further
    signals are computed.
    """
    if category_a != category_b:
        return 0, [], False, None
    score = 0
    same_place = place_a == place_b
    if same_place:
        score += 5
    kw_a = _tokenize(description_a)
    kw_b = _tokenize(description_b)
    shared = sorted(kw_a & kw_b)
    score += len(shared)
    days_apart = abs((date_a - date_b).days)
    if days_apart <= 3:
        score += 3
    elif days_apart <= 7:
        score += 1
    return score, shared, same_place, days_apart


def suggest_for_item(
    session: Session,
    item: FoundItem,
    user: Optional[User],
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
    user: Optional[User],
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
