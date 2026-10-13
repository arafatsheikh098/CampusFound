"""Bangla UI: every key on the landing/login/signup pages is in both en and bn."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEMPLATES = Path("app/templates")


def _collect_template_keys() -> set[str]:
    keys = set()
    for html in TEMPLATES.rglob("*.html"):
        text = html.read_text()
        for m in re.findall(r't\(\s*"([^"\.]+\.[^"]+)"', text):
            keys.add(m)
    return keys


def _lang_keys() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for f in Path("app/i18n").glob("*.json"):
        d = json.loads(f.read_text())
        out[f.stem] = set(d.keys())
    return out


def test_every_template_key_is_translated():
    used = _collect_template_keys()
    keys = _lang_keys()
    for lang, available in keys.items():
        missing = used - available
        assert not missing, f"keys used in templates but missing in {lang}: {missing}"


def test_landing_page_in_bangla(client: TestClient):
    # Switch language to bn via the form (cookies persist on client).
    r = client.get("/")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    csrf = m.group(1) if m else ""
    r = client.post("/lang/bn", data={"csrf_token": csrf})
    r = client.get("/")
    # Site title in Bangla.
    assert "ক্যাম্পাসফাউন্ড" in r.text
    # Log in / Sign up links in Bangla.
    assert "লগইন" in r.text
    assert "নিবন্ধন" in r.text


def test_404_page_in_bangla(client: TestClient):
    r = client.get("/")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    csrf = m.group(1) if m else ""
    client.post("/lang/bn", data={"csrf_token": csrf})
    r = client.get("/no-such-page-zzz")
    assert "পাওয়া যায়নি" in r.text
