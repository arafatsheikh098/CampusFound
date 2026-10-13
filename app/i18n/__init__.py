"""Translation helper.

``t("key", lang="en")`` looks up the key in the chosen dictionary, falling
back to English if the key is missing in the target language. Missing keys
in English raise ``KeyError`` so tests catch them.

The set of languages is fixed: ``en`` and ``bn``. The two JSON files
MUST have identical keys (test ``tests/test_i18n_keys.py``).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

I18N_DIR = Path(__file__).resolve().parent
LANGUAGES: List[str] = ["en", "bn"]
DEFAULT_LANG = "en"


@lru_cache(maxsize=None)
def _load(lang: str) -> Dict[str, str]:
    path = I18N_DIR / f"{lang}.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def available_keys(lang: str) -> set:
    return set(_load(lang).keys())


def t(key: str, lang: str = DEFAULT_LANG, **params) -> str:
    """Return the translation for ``key`` in ``lang``.

    Falls back to English, then to the key itself (with a single trailing
    dot) so the UI never crashes on a missing key. ``**params`` are
    substituted via ``str.format`` when the value uses ``{name}``-style
    placeholders.
    """
    d = _load(lang)
    if key in d:
        text = d[key]
    else:
        en = _load(DEFAULT_LANG)
        if key in en:
            text = en[key]
        else:
            return f"{key}."
    if params and "{" in text:
        try:
            return text.format(**params)
        except (KeyError, IndexError):
            return text
    return text


def languages() -> List[str]:
    return list(LANGUAGES)
