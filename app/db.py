"""SQLModel engine + session helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


def _make_engine():
    s = get_settings()
    url = s.database_url
    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(url, echo=False, connect_args=connect_args)


engine = _make_engine()


def init_db() -> None:
    """Create all tables (used in tests and the demo seed)."""
    # Import models so they register on the metadata
    import app.models  # noqa: F401
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for scripts (CLI, tests)."""
    with Session(engine) as session:
        yield session
