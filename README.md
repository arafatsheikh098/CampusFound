# CampusFound

A campus lost-and-found web app: members post items they have found, the
community claims them by answering short verification questions, and a
moderator approves the handover. Built as a privacy-respecting
FastAPI/SQLModel application with English and Bangla UI.

## Screenshots

A picture is worth a thousand lines of docs. Here's what the running app
actually looks like (captured from a local instance with `seed-demo`
data — see [docs/screenshots/](docs/screenshots/) for the full set).

| Landing | Browse items |
| --- | --- |
| ![Landing](docs/screenshots/01-landing.png) | ![Browse items](docs/screenshots/04-browse-items.png) |

| Item detail (as claimant) | Claim form |
| --- | --- |
| ![Item detail](docs/screenshots/05b-item-detail-claimable.png) | ![Claim form](docs/screenshots/06-claim-form.png) |

| Lost report | Moderation dashboard |
| --- | --- |
| ![Lost report](docs/screenshots/07-lost-report.png) | ![Moderation](docs/screenshots/09-moderation-dashboard.png) |

| English | Bangla |
| --- | --- |
| ![English landing](docs/screenshots/01-landing.png) | ![Bangla landing](docs/screenshots/11-landing-bangla.png) |

### Demo GIF (placeholder)

> **Status:** not yet recorded. A 15–30 s screen capture walking through
> "post a found item → claim it with a question → moderator approves" would
> sit here. Recording instructions:
>
> 1. Run the app locally with `seed-demo` data (see Quick start below).
> 2. Use `ffmpeg -f avfoundation -i "1" -t 30 demo.gif` (macOS) or any
>    screen recorder.
> 3. Convert with `ffmpeg -i demo.mov -vf "fps=15,scale=900:-1" demo.gif`.
> 4. Save the result as `docs/screenshots/demo.gif` and replace this
>    placeholder with `![Demo](docs/screenshots/demo.gif)`.

## Features

- Signup with Bangladesh mobile number, gated by moderator approval
- Post found items with category, place, date, description and 1-3
  verification questions
- Search and browse open items (Bangla keyword search works)
- Claim a found item by answering the verification questions
- Finder or moderator approves a claim; both parties confirm handover
- Lost-reports: members can describe what they lost and get suggested
  matches
- Photos with EXIF strip and 1600px / 200KB limits
- Notifications (in-app) and optional Telegram bot integration
- Moderation dashboard: approve/reject/suspend users, hide/restore items
- Privacy operations: `purge` and `delete-my-data` CLI subcommands
- English and Bangla UI with identical i18n keys
- Security headers (CSP, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy)
- Custom 404/500 pages
- `DEMO_MODE` banner for safe demo deployments

## Quick start (local)

```bash
# 1. Clone, then in the project root:
python3.12 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements-dev.txt

# 2. Configure
cp .env.example .env
# Edit SECRET_KEY for production use.

# 3. Database
.venv/bin/alembic upgrade head

# 4. Optional: load demo data
.venv/bin/python -m app.cli seed-demo
# (creates a moderator +8801711111111 / modpass12 and two members)

# 5. Run
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
# Open http://127.0.0.1:8000/
# (If you'd like to regenerate the README screenshots, see
#  docs/screenshots/README.md.)

# 6. Tests
.venv/bin/python -m pytest -q

# 7. Lint
.venv/bin/ruff check .
```

The first user to sign up normally will be in `PENDING` status. A
moderator must approve them. For local exploration, run
`seed-demo` to get a moderator immediately.

## Quick start (Docker)

```bash
docker compose up --build
# Open http://127.0.0.1:8000/
# Demo data is auto-loaded on first run (DEMO_MODE=1 in compose).
```

The compose file uses Postgres 16. To run with SQLite locally, use the
"Quick start (local)" flow above.

## CLI

```
.venv/bin/python -m app.cli create-moderator --full-name "..." --mobile "..." --password "..." --department "..." --session "..."
.venv/bin/python -m app.cli seed-demo       # idempotent
.venv/bin/python -m app.cli purge           # delete items >90 days old
.venv/bin/python -m app.cli delete-my-data <user_id>
```

## Project layout

```
app/
  main.py            # FastAPI app factory
  config.py          # settings (pydantic-settings)
  db.py              # SQLModel engine + session_scope()
  security.py        # password hashing, CSRF, session cookie signing
  deps.py            # current_user / require_member / require_moderator
  audit.py           # audit-log writer
  cli.py             # create-moderator / seed-demo / purge / delete-my-data
  auth/              # signup, login, logout, recovery
  places/, categories/, items/, photos/, claims/, lost/, matching/
  moderation/        # moderator dashboard
  notifications/     # in-app + telegram
  i18n/              # en.json, bn.json
  templates/         # Jinja2 templates
  static/htmx/       # vendored HTMX (no CDN)
alembic/             # migrations
tests/               # pytest test suite
scripts/             # fresh_clone.sh, smoke_test.sh
```

## Configuration (`.env`)

| Variable | Default | Description |
| --- | --- | --- |
| `ENV` | `development` | `development` or `production` |
| `SECRET_KEY` | placeholder | **Change in production.** Used to sign session cookies. |
| `DATABASE_URL` | `sqlite:///./campusfound.db` | SQLAlchemy URL. For Postgres: `postgresql+psycopg://user:pass@host:5432/db` |
| `TRUSTED_HOSTS` | `*` | Comma-separated trusted proxy IPs/CIDRs |
| `DAYS_DATE_FOUND_MAX` | `60` | Items older than this are auto-`UNCLAIMED` |
| `DAYS_CLAIM_EXPIRY` | `7` | Unreviewed claims expire after this many days |
| `DAYS_PURGE_AFTER` | `90` | Items are purged this many days after return/expiry |
| `TELEGRAM_BOT_TOKEN` | _empty_ | Optional. Leave empty to disable Telegram. |
| `TELEGRAM_WEBHOOK_SECRET` | _empty_ | Webhook path secret |
| `DEMO_MODE` | `0` | `1` shows the demo banner |

## Security notes

- Passwords are hashed with argon2id (argon2-cffi).
- CSRF tokens are bound to a per-session `cf_sid` cookie (HMAC-SHA256).
- CSP forbids inline scripts (`script-src 'self'`); HTMX is vendored
  under `static/htmx/htmx.min.js`.
- `frame-ancestors 'none'` and `X-Frame-Options: DENY` prevent
  clickjacking.
- Login attempts are rate-limited (see `app/security.py`).
- Photos are re-encoded through Pillow; EXIF is stripped.
- Recovery codes are one-time use and hashed at rest.

## Privacy notes

- No student ID numbers, no addresses, no precise GPS coordinates are
  collected.
- Verified-claimant contact details are only revealed after a claim is
  approved (see F6 in `SCOPE.md`).
- Audit rows never store raw answers or contact info.
- `purge` deletes items, claims, photos and answers older than
  `DAYS_PURGE_AFTER` days; audit rows are kept (without PII).
- `delete-my-data <user_id>` removes a user's posts, claims, photos
  and notifications; the user's name in audit rows is replaced with
  `deleted-user`.

## Development

```
# Run the test suite
.venv/bin/python -m pytest -q

# Lint
.venv/bin/ruff check .

# Auto-format
.venv/bin/ruff format .

# Run the fresh-clone test (in a tmp dir)
bash scripts/fresh_clone.sh

# Manual smoke
.venv/bin/python -m uvicorn app.main:app --port 8000
curl -i http://127.0.0.1:8000/health
```

CI runs on Postgres 16 (see `.github/workflows/ci.yml`).

## Languages

- `app/i18n/en.json` — English
- `app/i18n/bn.json` — Bangla

Both files must have identical keys. A test enforces parity.

## License

Internal / private. See `SCOPE.md` for the full feature contract.
