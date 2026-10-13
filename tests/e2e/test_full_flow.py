"""End-to-end test of the full happy path: sign up → moderator approval
→ post found item → claim → approve → confirm returned.

Drives the app via FastAPI's TestClient. This complements the unit
tests with a single test that exercises the complete user journey.
"""
from __future__ import annotations

import re
from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import select

from app.db import session_scope
from app.models.category import Category
from app.models.claim import Claim, ClaimStatus
from app.models.item import FoundItem, ItemStatus
from app.models.place import Place
from app.models.user import User


def _csrf(r) -> str:
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    return m.group(1) if m else ""


def test_full_happy_path(client: TestClient):
    # 1. Two members sign up.
    r = client.get("/")
    csrf = _csrf(r)
    r = client.post(
        "/signup",
        data={
            "full_name": "F Finder",
            "department": "CSE",
            "batch_or_session": "2024",
            "mobile": "+8801711111111",
            "password": "finder123",
            "is_member_confirmed": "1",
            "is_adult_confirmed": "1",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    # Signup renders the pending page (200), not a redirect.
    assert r.status_code == 200
    assert "pending" in r.text.lower() or "approval" in r.text.lower()
    r = client.post(
        "/signup",
        data={
            "full_name": "C Claimant",
            "department": "CSE",
            "batch_or_session": "2024",
            "mobile": "+8801722222222",
            "password": "claim123",
            "is_member_confirmed": "1",
            "is_adult_confirmed": "1",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert r.status_code == 200

    # 2. Moderator account created via CLI.
    from app import cli

    cli.main([
        "create-moderator",
        "--full-name", "M Mod",
        "--department", "CSE",
        "--session", "2020",
        "--mobile", "+8801799999999",
        "--password", "modpass12",
    ])

    # 3. Moderator logs in and approves both pending users.
    r = client.get("/login")
    csrf = _csrf(r)
    r = client.post(
        "/login",
        data={"identifier": "+8801799999999", "password": "modpass12",
              "csrf_token": csrf},
        follow_redirects=False,
    )
    print("DEBUG login status:", r.status_code, r.text[:300])
    assert r.status_code == 302  # logged in
    # Fetch the dashboard
    r = client.get("/moderation")
    assert r.status_code == 200
    csrf = _csrf(r)
    # Approve the finder
    with session_scope() as s:
        u = s.exec(select(User).where(User.mobile == "+8801711111111")).one()
        finder_id = u.id
    r = client.post(
        f"/moderation/users/{finder_id}/status",
        data={"csrf_token": csrf, "new_status": "approved"},
        follow_redirects=False,
    )
    assert r.status_code == 302

    # 4. Finder logs in and posts a found item.
    r = client.get("/")
    csrf = _csrf(r)
    r = client.post(
        "/login",
        data={"identifier": "+8801711111111", "password": "finder123",
              "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 302
    # Create a category + place (moderator did not seed them in the test
    # run, so insert via service directly).
    with session_scope() as s:
        if s.exec(select(Category).where(Category.name == "Wallet")).one_or_none() is None:
            s.add(Category(name="Wallet", sensitive=False, is_active=True))
        if s.exec(select(Place).where(Place.name == "Library")).one_or_none() is None:
            s.add(Place(name="Library", is_active=True))
        s.commit()
        cat = s.exec(select(Category).where(Category.name == "Wallet")).one()
        place = s.exec(select(Place).where(Place.name == "Library")).one()
        cat_id, place_id = cat.id, place.id
    r = client.get("/items/new")
    csrf = _csrf(r)
    r = client.post(
        "/items",
        data={
            "category_id": str(cat_id),
            "place_id": str(place_id),
            "date_found": date.today().isoformat(),
            "description": "Brown wallet",
            "handover_note": "",
            "custody": "finder",
            "q1": "What is the inner color?",
            "a1": "red",
            "q2": "",
            "a2": "",
            "q3": "",
            "a3": "",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    if r.status_code != 302:
        open("/tmp/e2e_fail.html", "w").write(r.text)
    assert r.status_code == 302, f"create item got {r.status_code}: see /tmp/e2e_fail.html"
    # Find the item
    with session_scope() as s:
        item = s.exec(select(FoundItem)).first()
        assert item is not None
        item_id = item.id

    # 5. Approve the claimant too. Finder logged in last, so we must
    #    log out and log back in as the moderator.
    r = client.post("/logout", data={"csrf_token": csrf}, follow_redirects=False)
    # /logout requires the moderator's csrf; we no longer have it.
    # Instead, log in as moderator to overwrite the session cookie.
    r = client.get("/login")
    csrf = _csrf(r)
    r = client.post(
        "/login",
        data={"identifier": "+8801799999999", "password": "modpass12",
              "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 302
    r = client.get("/moderation")
    assert r.status_code == 200
    csrf = _csrf(r)
    with session_scope() as s:
        u = s.exec(select(User).where(User.mobile == "+8801722222222")).one()
        claimant_id = u.id
    r = client.post(
        f"/moderation/users/{claimant_id}/status",
        data={"csrf_token": csrf, "new_status": "approved"},
        follow_redirects=False,
    )
    assert r.status_code == 302

    # 6. Claimant logs in, opens a claim, fills answers.
    r = client.get("/")
    csrf = _csrf(r)
    r = client.post(
        "/login",
        data={"identifier": "+8801722222222", "password": "claim123",
              "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 302
    r = client.get(f"/items/{item_id}/claim")
    assert r.status_code == 200
    csrf = _csrf(r)
    r = client.post(
        f"/items/{item_id}/claim",
        data={
            "note": "I lost this",
            "a1": "red",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    with session_scope() as s:
        cl = s.exec(select(Claim).where(Claim.item_id == item_id)).one()
        claim_id = cl.id

    # 7. Finder (re-logs in) approves the claim.
    r = client.get("/")
    csrf = _csrf(r)
    r = client.post(
        "/login",
        data={"identifier": "+8801711111111", "password": "finder123",
              "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 302
    r = client.get(f"/claims/{claim_id}/review")
    csrf = _csrf(r)
    r = client.post(
        f"/claims/{claim_id}/approve",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 302

    # 8. Both parties confirm returned.
    r = client.post(
        f"/claims/{claim_id}/confirm-returned",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 302
    r = client.get("/")
    csrf = _csrf(r)
    r = client.post(
        "/login",
        data={"identifier": "+8801722222222", "password": "claim123",
              "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 302
    r = client.get(f"/claims/{claim_id}")
    csrf = _csrf(r)
    r = client.post(
        f"/claims/{claim_id}/confirm-returned",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 302

    # 9. Item is now returned.
    with session_scope() as s:
        it = s.get(FoundItem, item_id)
        assert it.status == ItemStatus.RETURNED
        cl = s.get(Claim, claim_id)
        assert cl.status == ClaimStatus.COMPLETED
