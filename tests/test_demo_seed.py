"""seed-demo CLI: idempotent, inserts the demo categories/places/users/items."""
from __future__ import annotations

from sqlmodel import select

from app import cli
from app.db import session_scope
from app.models.category import Category
from app.models.item import FoundItem
from app.models.place import Place
from app.models.user import User


def test_seed_demo_inserts_categories_and_places():
    rc = cli.main(["seed-demo"])
    assert rc == 0
    with session_scope() as s:
        cat_names = {c.name for c in s.exec(select(Category)).all()}
        place_names = {p.name for p in s.exec(select(Place)).all()}
    assert "Wallets" in cat_names
    assert "ID cards" in cat_names
    assert "Library" in place_names
    assert "Cafeteria" in place_names


def test_seed_demo_creates_moderator_and_members():
    cli.main(["seed-demo"])
    with session_scope() as s:
        mod = s.exec(
            select(User).where(User.mobile == "+8801711111111")
        ).one_or_none()
        assert mod is not None
        assert mod.is_moderator
        assert mod.status.value == "approved"
        m1 = s.exec(
            select(User).where(User.mobile == "+8801722222222")
        ).one_or_none()
        m2 = s.exec(
            select(User).where(User.mobile == "+8801733333333")
        ).one_or_none()
        assert m1 is not None
        assert m2 is not None


def test_seed_demo_creates_demo_items():
    cli.main(["seed-demo"])
    with session_scope() as s:
        items = s.exec(select(FoundItem)).all()
        # The seed should add at least 2 demo items.
        assert len(items) >= 2


def test_seed_demo_is_idempotent():
    cli.main(["seed-demo"])
    with session_scope() as s:
        first_items = len(s.exec(select(FoundItem)).all())
    cli.main(["seed-demo"])
    with session_scope() as s:
        second_items = len(s.exec(select(FoundItem)).all())
    # Running the seed a second time does NOT add another batch of items.
    assert second_items == first_items
