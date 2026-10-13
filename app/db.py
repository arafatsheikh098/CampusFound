"""SQLModel engine + session helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


def _make_engine(url: str | None = None):
    s = get_settings()
    final_url = url or s.database_url
    connect_args: dict = {}
    pool = None
    if final_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        # In-memory SQLite benefits from a StaticPool so multiple sessions
        # see the same database. File-based SQLite uses the default pool.
        if ":memory:" in final_url or final_url.endswith(":memory:"):
            pool = StaticPool
    return create_engine(
        final_url,
        echo=False,
        connect_args=connect_args,
        poolclass=pool,
    )


engine = _make_engine()


def init_db() -> None:
    """Create all tables (used in tests and the demo seed)."""
    import app.models  # noqa: F401
    SQLModel.metadata.create_all(engine)


def reset_engine(url: str) -> None:
    """Replace the global engine (used by tests)."""
    global engine
    engine = _make_engine(url)
    init_db()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for scripts (CLI, tests). Expire-on-commit is off
    so objects can be read after the context exits.
    """
    sess = Session(engine, expire_on_commit=False)
    try:
        yield sess
    finally:
        sess.close()
