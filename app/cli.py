"""Command-line interface: ``python -m app.cli <subcommand>``.

Subcommands added incrementally per milestone:

- ``create-moderator`` (M2)
- ``seed-demo``        (M9)
- ``purge``            (M8)
- ``delete-my-data``   (M8)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlmodel import Session

from app.audit import write_audit
from app.auth.service import create_moderator
from app.config import get_settings
from app.db import engine, init_db, session_scope


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("create-moderator", help="create an approved moderator account")
    p.add_argument("--full-name", required=True)
    p.add_argument("--department", required=True)
    p.add_argument("--session", required=True, help="batch or session label")
    p.add_argument("--mobile", required=True, help="Bangladesh mobile number")
    p.add_argument("--password", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "create-moderator":
        return cmd_create_moderator(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
