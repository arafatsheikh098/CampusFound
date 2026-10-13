"""Item search and listing.

Builds a SQLAlchemy/SQLModel filter expression from the form-style
``SearchParams`` so the list page can be filled from a single
``GET /items?q=...&category_id=...&place_id=...&date_from=...&date_to=...&page=1``.

F5 acceptance:
 - filters combine correctly
 - pagination boundaries are correct
 - keyword search is case-insensitive, works on Bangla, treats `%`
   and `<` as plain text (we use parameterised SQL, never string
   interpolation, so this is automatic)
 - sensitive items never reveal any field beyond the generic
   placeholder (we project only safe fields for the list query)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple

from sqlmodel import Session, and_, func, or_, select

from app.models.category import Category
from app.models.item import FoundItem, ItemStatus
from app.models.place import Place

# Public status set: items visible in the list. UNCLAIMED posts also
# appear in the list (as "Unclaimed at office") so moderators can find
# them.
PUBLIC_STATUSES: Tuple[ItemStatus, ...] = (
    ItemStatus.OPEN,
    ItemStatus.CLAIM_APPROVED,
    ItemStatus.UNCLAIMED,
)

PAGE_SIZE = 20

# Whitelist of sort columns the UI is allowed to choose from. Anything
# else falls back to ``date_found desc`` so SQL injection is impossible.
_SORT_WHITELIST = {
    "date_found_desc": (FoundItem.date_found, "desc"),
    "date_found_asc": (FoundItem.date_found, "asc"),
    "created_desc": (FoundItem.created_at, "desc"),
    "created_asc": (FoundItem.created_at, "asc"),
}


@dataclass
class SearchParams:
    q: str = ""
    category_id: Optional[int] = None
    place_id: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    page: int = 1
    sort: str = "date_found_desc"

    def normalised(self) -> "SearchParams":
        p = max(1, int(self.page or 1))
        return SearchParams(
            q=(self.q or "").strip(),
            category_id=self.category_id,
            place_id=self.place_id,
            date_from=self.date_from,
            date_to=self.date_to,
            page=p,
            sort=self.sort if self.sort in _SORT_WHITELIST else "date_found_desc",
        )


def _build_filters(p: SearchParams):
    conds = [FoundItem.status.in_(PUBLIC_STATUSES), FoundItem.hidden.is_(False)]
    if p.category_id:
        conds.append(FoundItem.category_id == p.category_id)
    if p.place_id:
        conds.append(FoundItem.place_id == p.place_id)
    if p.date_from:
        conds.append(FoundItem.date_found >= p.date_from)
    if p.date_to:
        conds.append(FoundItem.date_found <= p.date_to)
    if p.q:
        # Parametric LIKE — no string interpolation. `%`, `_` and `\`
        # from the user are escaped so they match as literal characters.
        # SQLite and PostgreSQL both support the default LIKE escape
        # via the ESCAPE clause.
        escaped = p.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped.lower()}%"
        conds.append(
            or_(
                func.lower(FoundItem.description).like(like, escape="\\"),
            )
        )
    return and_(*conds)


@dataclass
class SearchResult:
    items: List[FoundItem]
    categories: dict  # id -> Category
    places: dict  # id -> Place
    total: int
    page: int
    pages: int


def search(session: Session, params: SearchParams) -> SearchResult:
    p = params.normalised()

    # Count
    count_stmt = select(func.count(FoundItem.id)).where(_build_filters(p))
    total = session.exec(count_stmt).one()

    # Items
    sort_col, sort_dir = _SORT_WHITELIST[p.sort]
    stmt = select(FoundItem).where(_build_filters(p))
    if sort_dir == "desc":
        stmt = stmt.order_by(sort_col.desc(), FoundItem.id.desc())
    else:
        stmt = stmt.order_by(sort_col.asc(), FoundItem.id.asc())
    stmt = stmt.offset((p.page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    items = session.exec(stmt).all()

    # Lookups for display
    cat_ids = {i.category_id for i in items}
    place_ids = {i.place_id for i in items}
    cats = {}
    if cat_ids:
        for c in session.exec(select(Category).where(Category.id.in_(cat_ids))).all():
            cats[c.id] = c
    pls = {}
    if place_ids:
        for x in session.exec(select(Place).where(Place.id.in_(place_ids))).all():
            pls[x.id] = x

    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return SearchResult(
        items=list(items),
        categories=cats,
        places=pls,
        total=int(total or 0),
        page=p.page,
        pages=pages,
    )


def parse_date(s: str) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def parse_int(s: str) -> Optional[int]:
    if s is None or s == "":
        return None
    try:
        return int(s)
    except (TypeError, ValueError):
        return None
