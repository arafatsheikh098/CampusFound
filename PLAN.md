# PLAN.md — milestones and file map

Each milestone lists the files it will create or modify and the tests it must add. After each milestone, the agent runs the Milestone Gate from `CLAUDE.md` and only then commits.

## M1 — Foundation and i18n scaffold
Files (create):
- `app/__init__.py`
- `app/main.py` (FastAPI app factory, `GET /health`)
- `app/config.py` (pydantic-settings, `.env.example`)
- `.env.example`
- `app/db.py` (SQLModel engine + session helpers)
- `app/models/__init__.py` (exports every entity from SCOPE)
- `app/models/user.py`
- `app/models/place.py`
- `app/models/category.py`
- `app/models/item.py`
- `app/models/photo.py`
- `app/models/claim.py`
- `app/models/lost_report.py`
- `app/models/notification.py`
- `app/models/audit.py`
- `app/models/recovery_code.py`
- `app/models/login_attempt.py`
- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/0001_init.py`
- `app/templates/base.html` (vendored HTMX, language toggle)
- `app/templates/health.html` (minimal)
- `app/i18n/__init__.py` (translation helper)
- `app/i18n/en.json`
- `app/i18n/bn.json`
- `app/phone.py` (normalization)
- `static/htmx/htmx.min.js` (vendored)
- `Dockerfile`
- `docker-compose.yml`
- `Makefile`
- `.github/workflows/ci.yml`
- `pytest.ini`
- `tests/conftest.py`
- `tests/test_health.py`
- `tests/test_phone.py`
- `tests/test_i18n_keys.py`
- `tests/test_migrations.py`

Acceptance: SCOPE §F11.1, F11.6, F11.8 (partial), §Global 1–3.

## M2 — Accounts, moderator approval, security baseline
Files:
- `app/security.py` (session signing, CSRF, rate limit)
- `app/deps.py` (`require_member`, `require_moderator`, current user)
- `app/audit.py` (audit-log writer)
- `app/cli.py` (`create-moderator`, `seed-demo`, `purge`, `delete-my-data`)
- `app/auth/routes.py`
- `app/auth/templates/login.html`, `signup.html`, `pending.html`, `suspended.html`, `recovery.html`
- `tests/test_auth.py`, `test_csrf.py`, `test_rate_limit.py`, `test_recovery_codes.py`, `test_suspension.py`, `test_secret_key.py`

Acceptance: §F1, §F8 (state-changing routes).

## M3 — Locations, categories, found-item posts
Files:
- `app/places/routes.py` and templates
- `app/categories/routes.py` and templates
- `app/items/routes.py` and templates (create/view/edit/withdraw — no photos yet)
- `app/items/schemas.py`
- `tests/test_places.py`, `test_categories.py`, `test_items.py`, `test_item_sensitive.py`, `test_html_escape.py`

Acceptance: §F2, §F3.

## M4 — Photo pipeline
Files:
- `app/photos/processing.py` (validate, strip, re-encode)
- `app/photos/routes.py` (upload, serve)
- `app/models/photo.py` columns finalized
- `tests/test_photo_pipeline.py` (crafted files), `test_photo_serving.py`, `test_photo_deletion.py`

Acceptance: §F4.

## M5 — Browse and search
Files:
- `app/items/search.py`
- `app/items/templates/list.html`, `search.html`
- `tests/test_browse.py`, `test_search.py`, `test_sensitive_list.py`, `test_unclaimed_boundary.py`

Acceptance: §F5.

## M6 — Claims, decisions, handover
Files:
- `app/claims/routes.py`, `app/claims/schemas.py`, `app/claims/service.py`
- templates: `claim_new.html`, `claim_review.html`, `claim_approved.html`
- `tests/test_claim_limits.py` (concurrent), `test_claim_review.py`, `test_contact_reveal.py`, `test_handover.py`, `test_claim_expiry.py`, `test_audit_rows.py`

Acceptance: §F6, §F7.

## M7 — Lost reports and matching
Files:
- `app/lost/routes.py` and templates
- `app/matching/__init__.py` (pure function)
- `app/matching/suggest.py`
- `tests/test_lost_reports.py`, `test_matching.py`, `test_matching_purity.py`, `test_matching_visibility.py`

Acceptance: §F8.

## M8 — Moderation, notifications, privacy operations
Files:
- `app/moderation/routes.py` and templates
- `app/notifications/routes.py` and templates
- `app/notifications/telegram.py`
- `app/audit.py` (extensions)
- `app/cli.py` (purge, delete-my-data)
- `tests/test_moderation.py`, `test_notifications.py`, `test_telegram.py`, `test_purge.py`, `test_delete_my_data.py`, `test_log_capture.py`

Acceptance: §F9, §F10, §F11 (except seed and Bangla completion).

## M9 — Seed, Bangla UI, E2E tests
Files:
- complete `app/i18n/bn.json` keys
- `app/templates/errors/404.html`, `500.html`
- `app/security_headers.py`
- `app/cli.py` (`seed-demo` idempotent)
- `tests/test_security_headers.py`
- `tests/test_demo_seed.py` (idempotence)
- `tests/e2e/test_full_flow.py` (Playwright)
- `docs/screenshots/*.png` (Playwright captures)

Acceptance: §F11.2, F11.3, F11.7, E2E flow.
