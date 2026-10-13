#!/usr/bin/env bash
# Fresh-clone test: verify a new contributor can set up the project from
# a clean checkout using only the README and Makefile.
#
# What it does:
#   1. Creates a temporary copy of the project (excluding .venv, db, etc.)
#   2. Creates a fresh Python venv
#   3. Installs requirements
#   4. Runs alembic upgrade head
#   5. Runs the test suite
#   6. Starts the app and curls /health, /, a 404 page
#
# Exits 0 on success, non-zero on any failure.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d -t campusfound-fresh.XXXXXX)"
echo "==> fresh-clone test in $TMP"

# Copy project, skipping state and build artifacts.
rsync -a --exclude='.venv' --exclude='.pytest_cache' --exclude='.ruff_cache' \
  --exclude='__pycache__' --exclude='*.db' --exclude='.git' --exclude='node_modules' \
  "$ROOT/" "$TMP/"

cd "$TMP"

PY=python3.12
if ! command -v "$PY" >/dev/null 2>&1; then
  PY=python3
fi
echo "==> using $PY"
$PY --version

echo "==> create venv"
$PY -m venv .venv
.venv/bin/pip install -U pip >/dev/null
.venv/bin/pip install -r requirements-dev.txt

echo "==> alembic upgrade head"
.venv/bin/alembic upgrade head

echo "==> seed demo"
.venv/bin/python -m app.cli seed-demo
.venv/bin/python -m app.cli seed-demo  # idempotent

echo "==> run tests"
.venv/bin/python -m pytest -q

echo "==> smoke: start app in background, curl /health and /"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 &
APP_PID=$!
trap 'kill $APP_PID 2>/dev/null || true' EXIT
# Wait for app to be ready.
for i in $(seq 1 30); do
  if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/health | grep -q "200"; then
    break
  fi
  sleep 0.5
done

echo "==> /health"
curl -s -i http://127.0.0.1:8765/health | head -5
echo "==> /"
curl -s -i http://127.0.0.1:8765/ | head -5
echo "==> /no-such-page-xyz (404)"
curl -s -o /dev/null -w "status=%{http_code}\n" http://127.0.0.1:8765/no-such-page-xyz

echo "==> fresh-clone test OK"
