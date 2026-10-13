"""Pure matching score function.

No database or web imports — this module is the unit-testable core
of the matching algorithm. The DB-using helpers live in
``app.matching.suggest`` and depend on this module.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Set, Tuple

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
