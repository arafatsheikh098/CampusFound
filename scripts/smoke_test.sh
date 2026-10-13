#!/usr/bin/env bash
# Smoke test: start the app on a free port, hit a few URLs, then stop it.
# Used by the make `smoke` target and as a quick CI check.
set -euo pipefail

PORT="${1:-8765}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" &
APP_PID=$!
trap 'kill $APP_PID 2>/dev/null || true' EXIT

# Wait up to 15s for the app to come up.
for _ in $(seq 1 30); do
  if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:"$PORT"/health | grep -q "200"; then
    break
  fi
  sleep 0.5
done

echo "GET /health"
curl -s -i "http://127.0.0.1:$PORT/health" | head -1
echo "GET /"
curl -s -o /dev/null -w "status=%{http_code} content-type=%{content_type}\n" "http://127.0.0.1:$PORT/"
echo "GET /no-such-page (404)"
curl -s -o /dev/null -w "status=%{http_code}\n" "http://127.0.0.1:$PORT/no-such-page"

echo "OK"
