"""Command-line interface: ``python -m app.cli <subcommand>``.

Subcommands:

- ``create-moderator``   create an approved moderator account
- ``seed-demo``          insert a small demo dataset (idempotent)
- ``purge``              hard-delete items/users past retention
- ``delete-my-data``     delete everything tied to one mobile number
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from app.audit import write_audit
from app.auth.service import create_moderator
from app.config import get_settings
from app.db import engine, init_db, session_scope
from app.models.category import Category
from app.models.claim import Claim
from app.models.item import FoundItem, ItemStatus
from app.models.lost_report import LostReport
from app.models.place import Place
from app.models.user import AccountStatus, User


def cmd_create_moderator(args: argparse.Namespace) -> int:
    init_db()
    with session_scope() as session:
        try:
            user = create_moderator(
                session,
                full_name=args.full_name,
                department=args.department,
                batch_or_session=args.session,
                mobile=args.mobile,
                password=args.password,
            )
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        write_audit(
            session,
            actor_id=user.id,
            actor_label=user.full_name,
            action="moderator_created",
            target_kind="user",
            target_id=user.id,
        )
        session.commit()
    print(f"created moderator id={user.id} mobile={user.mobile}")
    return 0


def cmd_purge(args: argparse.Namespace) -> int:
    """Hard-delete items/users past their retention.

    Items: status in (returned, withdrawn) older than days_purge_after.
    Users: suspended or rejected older than days_purge_after.
    Audit log is never modified.
    """
    init_db()
    settings = get_settings()
    cutoff = datetime.utcnow() - timedelta(days=settings.days_purge_after)
    deleted_items = 0
    deleted_users = 0
    with session_scope() as session:
        # Hard-delete items that are in terminal states AND have an
        # associated terminal timestamp older than cutoff.
        for status, ts_attr in (
            (ItemStatus.RETURNED, "returned_at"),
            (ItemStatus.WITHDRAWN, "withdrawn_at"),
            (ItemStatus.UNCLAIMED, "unclaimed_at"),
        ):
            rows = session.exec(select(FoundItem).where(FoundItem.status == status)).all()
            for r in rows:
                ts = getattr(r, ts_attr, None) or r.updated_at
                if ts is not None and ts < cutoff:
                    # Drop photos
                    from app.photos.service import delete_photos_for_item

                    delete_photos_for_item(session, r)
                    # Drop related rows
                    for cl in session.exec(
                        select(Claim).where(Claim.item_id == r.id)
                    ).all():
                        session.delete(cl)
                    session.delete(r)
                    deleted_items += 1
        session.commit()

        # Drop old rejected/suspended users (no audit/mod actions in 90d).
        rows = session.exec(select(User).where(User.status.in_(
            (AccountStatus.REJECTED, AccountStatus.SUSPENDED)
        ))).all()
        for u in rows:
            ts = u.suspended_at or u.created_at
            if ts is not None and ts < cutoff:
                # Drop the user (cascading rules in models).
                session.delete(u)
                deleted_users += 1
        session.commit()
    print(f"purged items={deleted_items} users={deleted_users}")
    return 0


def cmd_delete_my_data(args: argparse.Namespace) -> int:
    """Delete every row tied to ``--mobile``.

    Snapshots the user's name into audit_log so historical entries
    remain attributable. Photos and items are also dropped.
    """
    init_db()
    from app.phone import normalize

    mobile = normalize(args.mobile)
    with session_scope() as session:
        u = session.exec(select(User).where(User.mobile == mobile)).one_or_none()
        if u is None:
            print("no user with that mobile", file=sys.stderr)
            return 2
        # Write the audit trail BEFORE deleting the user so we keep the
        # id-mapping and a snapshot of the name. The actor is the user
        # themselves; we capture "deleted_user" as actor_label.
        write_audit(
            session,
            actor_id=None,
            actor_label=f"deleted_user:{u.id}",
            action="user_data_deleted",
            target_kind="user",
            target_id=u.id,
            extra={"mobile_snapshot": mobile},
        )
        # Delete their items (cascades to questions, claims, photos).
        for item in session.exec(
            select(FoundItem).where(FoundItem.finder_id == u.id)
        ).all():
            from app.photos.service import delete_photos_for_item

            delete_photos_for_item(session, item)
            for cl in session.exec(select(Claim).where(Claim.item_id == item.id)).all():
                session.delete(cl)
            session.delete(item)
        # Delete their lost reports.
        for lr in session.exec(
            select(LostReport).where(LostReport.owner_id == u.id)
        ).all():
            session.delete(lr)
        # Delete their claims (where they are the claimant).
        for cl in session.exec(
            select(Claim).where(Claim.claimant_id == u.id)
        ).all():
            session.delete(cl)
        # Finally the user.
        session.delete(u)
        session.commit()
    print("ok")
    return 0


def cmd_seed_demo(args: argparse.Namespace) -> int:
    """Insert a small deterministic demo dataset. Idempotent."""
    init_db()
    from app.items import service as item_svc

    now = datetime.utcnow()
    today = date.today()
    with session_scope() as session:
        # Categories: idempotent on (name).
        existing_cats = {
            c.name: c for c in session.exec(select(Category)).all()
        }
        demo_cats = [
            ("Wallets", False),
            ("Phones", False),
            ("ID cards", True),
            ("Books", False),
        ]
        for name, sensitive in demo_cats:
            if name not in existing_cats:
                session.add(Category(name=name, sensitive=sensitive, is_active=True))
        # Places
        existing_places = {p.name: p for p in session.exec(select(Place)).all()}
        for name in ("Library", "Cafeteria", "Lecture Hall A", "Sports Complex"):
            if name not in existing_places:
                session.add(Place(name=name, is_active=True))
        # Demo moderator
        if session.exec(
            select(User).where(User.mobile == "+8801711111111")
        ).one_or_none() is None:
            m = User(
                full_name="Demo Mod",
                department="CSE",
                batch_or_session="2020",
                mobile="+8801711111111",
                password_hash="x",  # placeholder; not used for login in demo
                is_member_confirmed=True,
                is_adult_confirmed=True,
                status=AccountStatus.APPROVED,
                is_moderator=True,
                approved_at=now,
                display_name_snapshot="Demo Mod",
            )
            session.add(m)
        # Two demo members
        members = []
        for i, mobile in enumerate(("+8801722222222", "+8801733333333"), start=1):
            existing = session.exec(
                select(User).where(User.mobile == mobile)
            ).one_or_none()
            if existing is None:
                u = User(
                    full_name=f"Demo Member {i}",
                    department="CSE",
                    batch_or_session="2024",
                    mobile=mobile,
                    password_hash="x",
                    is_member_confirmed=True,
                    is_adult_confirmed=True,
                    status=AccountStatus.APPROVED,
                    approved_at=now,
                    display_name_snapshot=f"Demo Member {i}",
                )
                session.add(u)
                members.append(u)
            else:
                members.append(existing)
        session.commit()
        # Demo found items (only if the user has none yet).
        have_items = session.exec(
            select(FoundItem).where(FoundItem.finder_id == members[0].id)
        ).first()
        if have_items is None:
            wallet = session.exec(
                select(Category).where(Category.name == "Wallets")
            ).one_or_none()
            books = session.exec(
                select(Category).where(Category.name == "Books")
            ).one_or_none()
            library = session.exec(
                select(Place).where(Place.name == "Library")
            ).one_or_none()
            cafeteria = session.exec(
                select(Place).where(Place.name == "Cafeteria")
            ).one_or_none()
            if wallet and library:
                item_svc.create_item(
                    session,
                    finder=members[0],
                    category_id=wallet.id,
                    place_id=library.id,
                    date_found=today - timedelta(days=1),
                    description="Brown leather wallet, no ID inside",
                    handover_note="Meet at the library desk",
                    custody_requested="finder",
                    questions=["What color is the inner lining?"],
                    answers=["red"],
                )
            if books and cafeteria:
                item_svc.create_item(
                    session,
                    finder=members[1] if len(members) > 1 else members[0],
                    category_id=books.id,
                    place_id=cafeteria.id,
                    date_found=today - timedelta(days=2),
                    description="A copy of Clean Code, has a name on the first page",
                    handover_note="",
                    custody_requested="finder",
                    questions=["What name is written inside?"],
                    answers=["A. Karim"],
                )
            session.commit()
    print("seed-demo: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("create-moderator", help="create an approved moderator account")
    p.add_argument("--full-name", required=True)
    p.add_argument("--department", required=True)
    p.add_argument("--session", required=True, help="batch or session label")
    p.add_argument("--mobile", required=True, help="Bangladesh mobile number")
    p.add_argument("--password", required=True)

    p = sub.add_parser("seed-demo", help="insert a small idempotent demo dataset")
    p.set_defaults(func=cmd_seed_demo)

    p = sub.add_parser("purge", help="hard-delete terminal items and old users")
    p.set_defaults(func=cmd_purge)

    p = sub.add_parser("delete-my-data", help="delete every row tied to a mobile")
    p.add_argument("--mobile", required=True)
    p.set_defaults(func=cmd_delete_my_data)

    args = parser.parse_args(argv)
    if args.cmd == "create-moderator":
        return cmd_create_moderator(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
