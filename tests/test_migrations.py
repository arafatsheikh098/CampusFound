"""Migration tests: upgrade and downgrade work on SQLite and Postgres."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _run_alembic(*args, env=None):
    cmd = [sys.executable, "-m", "alembic", *args]
    e = os.environ.copy()
    if env:
        e.update({k: str(v) for k, v in env.items()})
    return subprocess.run(cmd, cwd=str(REPO), env=e, capture_output=True, text=True)


def test_upgrade_downgrade_sqlite(tmp_path):
    db = tmp_path / "m.db"
    env = {"DATABASE_URL": f"sqlite:///{db}"}
    up = _run_alembic("upgrade", "head", env=env)
    assert up.returncode == 0, up.stdout + up.stderr
    assert db.exists()

    down = _run_alembic("downgrade", "base", env=env)
    assert down.returncode == 0, down.stdout + down.stderr


@pytest.mark.skipif(
    not os.environ.get("POSTGRES_URL"),
    reason="POSTGRES_URL not set; skipping postgres migration test",
)
def test_upgrade_downgrade_postgres():
    url = os.environ["POSTGRES_URL"]
    up = _run_alembic("upgrade", "head", env={"DATABASE_URL": url})
    assert up.returncode == 0, up.stdout + up.stderr
    down = _run_alembic("downgrade", "base", env={"DATABASE_URL": url})
    assert down.returncode == 0, down.stdout + down.stderr
