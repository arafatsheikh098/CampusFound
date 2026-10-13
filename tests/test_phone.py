"""Phone normalization tests."""
from __future__ import annotations

import pytest

from app.phone import is_valid, normalize


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("01712345678", "+8801712345678"),
        ("+8801712345678", "+8801712345678"),
        ("8801712345678", "+8801712345678"),
        ("017-1234-5678", "+8801712345678"),
        ("017 1234 5678", "+8801712345678"),
        ("008801712345678", "+8801712345678"),
        ("+880 1712 345 678", "+8801712345678"),
        ("01912345678", "+8801912345678"),
        ("01312345678", "+8801312345678"),
        ("01412345678", "+8801412345678"),
        ("01512345678", "+8801512345678"),
        ("01612345678", "+8801612345678"),
        ("01812345678", "+8801812345678"),
    ],
)
def test_normalize_accepts_valid_formats(raw, expected):
    assert normalize(raw) == expected
    assert is_valid(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "01212345678",  # not a mobile prefix
        "02112345678",  # looks like a landline
        "8801712345",  # too short
        "880171234567890",  # too long
        "01712abc678",  # letters
        "",
        "   ",
        "+8801712345a78",
        "abc",
    ],
)
def test_normalize_rejects_invalid(raw):
    assert not is_valid(raw)
    with pytest.raises(ValueError):
        normalize(raw)
