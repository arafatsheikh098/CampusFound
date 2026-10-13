"""Purity test for the matching score function."""
from __future__ import annotations

from datetime import date

from app.matching.score import score_match


def test_score_module_has_no_db_or_web_imports():
    """F8.5: matching score must not import the web or DB layers."""
    import inspect

    import app.matching.score as score_mod

    src = inspect.getsourcefile(score_mod)
    assert src is not None
    text = open(src).read()
    for name in ("sqlmodel", "sqlalchemy", "fastapi", "starlette", "app.db", "app.models"):
        assert name not in text, f"score module references {name}"


def test_score_match_is_deterministic():
    a = dict(
        category_a=1, category_b=1, place_a=1, place_b=2,
        date_a=date(2026, 1, 1), date_b=date(2026, 1, 2),
        description_a="bottle", description_b="bottle cap",
    )
    # Same inputs -> same output, repeated.
    out1 = score_match(**a)
    out2 = score_match(**a)
    assert out1 == out2


def test_score_match_does_not_use_module_state():
    # Calling with different description text should yield different
    # keyword intersections and different scores.
    s1, kw1, _, _ = score_match(
        category_a=1, category_b=1, place_a=1, place_b=2,
        date_a=date(2026, 1, 1), date_b=date(2026, 1, 2),
        description_a="phone", description_b="phone",
    )
    s2, kw2, _, _ = score_match(
        category_a=1, category_b=1, place_a=1, place_b=2,
        date_a=date(2026, 1, 1), date_b=date(2026, 1, 2),
        description_a="umbrella", description_b="phone",
    )
    assert kw1 == ["phone"]
    assert kw2 == []
    assert s1 > s2
