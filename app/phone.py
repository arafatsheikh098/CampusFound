"""Bangladesh mobile phone number normalization.

Accepts the following inputs and returns the canonical E.164-style value
"+8801XXXXXXXXX" (13 characters):

    01712345678
    +8801712345678
    8801712345678
    017-1234-5678

Rejects:
- numbers starting with 012 (not a Bangladesh mobile prefix)
- landline-style numbers
- too short / too long input
- non-digit characters other than +, -, space

Public API:
    normalize(raw: str) -> str
    is_valid(raw: str) -> bool
"""
from __future__ import annotations

import re
from typing import Final

# Bangladesh mobile operator prefixes: 13, 14, 15, 16, 17, 18, 19
_BD_MOBILE_PREFIXES: Final = ("13", "14", "15", "16", "17", "18", "19")
# After country code 880 and a leading 0, 10 digits remain (operator 2 + subscriber 8).
_TOTAL_DIGITS: Final = 13  # "880" + 10 digits (operator 2 + subscriber 8)


# Allow +, digits, spaces, dashes
_RE_INPUT = re.compile(r"^[\+\d\-\s]+$")


def _digits_only(raw: str) -> str:
    return re.sub(r"[\s\-]", "", raw)


def is_valid(raw: str) -> bool:
    """Return True if the raw input is a valid Bangladesh mobile number."""
    try:
        normalize(raw)
        return True
    except ValueError:
        return False


def normalize(raw: str) -> str:
    """Normalize a Bangladesh mobile number to ``+8801XXXXXXXXX``.

    Raises ``ValueError`` for invalid input.
    """
    if not isinstance(raw, str):
        raise ValueError("phone must be a string")

    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("phone is empty")

    if not _RE_INPUT.match(cleaned):
        raise ValueError("phone contains invalid characters")

    digits = _digits_only(cleaned)
    # Drop a leading "+" that may have been carried
    if digits.startswith("+"):
        digits = digits[1:]

    if not digits.isdigit():
        raise ValueError("phone must contain only digits after cleaning")

    # Normalize prefixes
    if digits.startswith("+"):
        digits = digits[1:]

    if digits.startswith("00880"):
        digits = "880" + digits[5:]
    elif digits.startswith("880"):
        # already has country code
        pass
    elif digits.startswith("0"):
        digits = "880" + digits[1:]
    else:
        # No country code and no leading 0 — reject ambiguous inputs
        raise ValueError("phone must start with 0, 880 or +880")

    if len(digits) != _TOTAL_DIGITS:
        raise ValueError(
            f"phone must have {_TOTAL_DIGITS - 3} digits after the country code, got {len(digits) - 3}"
        )

    if not digits.startswith("880"):
        raise ValueError("phone country code must be 880")

    local = digits[3:]  # e.g. 1712345678
    if not local.startswith("1"):
        raise ValueError("Bangladesh mobile numbers must start with 1 after the country code")

    operator_prefix = local[:2]
    if operator_prefix not in _BD_MOBILE_PREFIXES:
        raise ValueError(
            f"phone operator prefix {operator_prefix!r} is not a valid Bangladesh mobile prefix"
        )

    return "+" + digits
