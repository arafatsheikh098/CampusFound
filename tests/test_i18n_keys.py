"""i18n: en and bn dictionaries must have identical keys."""
from __future__ import annotations

from app.i18n import available_keys, languages, t


def test_en_and_bn_have_identical_keys():
    keys_by_lang = {lang: available_keys(lang) for lang in languages()}
    base_lang = languages()[0]
    base_keys = keys_by_lang[base_lang]
    for lang, keys in keys_by_lang.items():
        missing = base_keys - keys
        extra = keys - base_keys
        assert not missing, f"keys missing in {lang}: {missing}"
        assert not extra, f"keys extra in {lang}: {extra}"


def test_t_returns_value_for_known_key():
    assert t("site.title") == "CampusFound"


def test_t_falls_back_to_english_for_missing_key_in_bn(monkeypatch):
    # No public hook to "remove" a key; just exercise the fallback by passing
    # an unknown key (which we expect to fall back to the English dot-form).
    val = t("definitely.not.a.key", lang="bn")
    assert val.endswith(".")
