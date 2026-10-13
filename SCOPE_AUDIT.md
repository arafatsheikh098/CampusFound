# SCOPE AUDIT — final

This file records the evidence that every acceptance criterion in
`SCOPE.md` is satisfied by the codebase as of the latest commit. It is
a snapshot for review only; it is not part of the running app.

| # | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| F1.1 | Signup → PENDING; login blocked with awaiting-approval message | PASS | `tests/test_auth.py::test_signup_creates_pending` |
| F1.2 | Passwords are argon2-cffi hashes (`$argon2$...`) | PASS | `tests/test_security.py::test_password_hash_format` |
| F1.3 | 6 failures in 15min → 429; freezegun time | PASS | `tests/test_rate_limit.py` |
| F1.4 | Single generic "invalid" path | PASS | `app/auth/service.py::login` |
| F1.5 | 10 recovery codes, shown once, hashed at rest | PASS | `tests/test_recovery_codes.py` |
| F1.6 | Moderator via CLI only | PASS | `tests/test_secret_key.py`, `app/cli.py::create-moderator` |
| F1.7 | Production refuses default SECRET_KEY | PASS | `tests/test_secret_key.py::test_production_refuses_default_secret_key` |
| F1.8 | Pending/rejected/suspended cannot log in; suspended session dies | PASS | `tests/test_suspension.py` |
| F2.1 | Moderator-only places/categories; non-mod gets 403 | PASS | `tests/test_places.py`, `tests/test_categories.py` |
| F2.2 | `sensitive` boolean, mod-only toggle | PASS | `app/models/category.py`, `tests/test_item_sensitive.py` |
| F2.3 | Sensitive → custody office (server enforcement) | PASS | `app/items/service.py::_enforce_sensitive`, `tests/test_item_sensitive.py` |
| F3.1 | date_found future / >60 days rejected (frozen time) | PASS | `tests/test_items.py::test_date_found_*` |
| F3.2 | description ≤ 300, HTML escaped | PASS | `tests/test_html_escape.py` |
| F3.3 | 1-3 questions, ≤ 120 each; answers ≤ 120 | PASS | `tests/test_items.py::test_questions_*` |
| F3.4 | handover_note ≤ 150 | PASS | `tests/test_items.py::test_handover_note_max` |
| F3.5 | Sensitive posts: no photos (server drops bytes) | PASS | `tests/test_photo_serving.py` |
| F3.6 | Private answers never rendered to non-owner / non-mod | PASS | scan tests in `tests/test_items.py` |
| F3.7 | Edit/withdraw: owner or mod only | PASS | `tests/test_items.py` |
| F4.1 | EXIF stripped | PASS | `tests/test_photo_pipeline.py::test_exif_stripped` |
| F4.2 | Reject text/.jpg, truncated, bomb, >5MB, SVG, polyglot, empty | PASS | `tests/test_photo_pipeline.py` |
| F4.3 | Photo endpoint: 404 to logged-out/pending/suspended; Cache-Control private; X-Content-Type-Options nosniff; Content-Disposition inline | PASS | `tests/test_photo_serving.py` |
| F4.4 | ≤ 2 photos; sensitive: 0 photos | PASS | `tests/test_photo_pipeline.py` |
| F4.5 | Withdraw / returned → photos deleted | PASS | `tests/test_photo_deletion.py` |
| F4.6 | Long side ≤ 1024 px | PASS | `tests/test_photo_pipeline.py` |
| F5.1 | Filter matrix and pagination | PASS | `tests/test_browse.py` |
| F5.2 | Case-insensitive, Bangla, `%`/`<` as text | PASS | `tests/test_search.py`, `tests/test_browse.py` |
| F5.3 | Sensitive list: generic text only | PASS | `tests/test_sensitive_list.py` |
| F5.4 | Logged-out item page: login, no leak | PASS | `tests/test_sensitive_list.py::test_logged_out_member_item_page_is_login` |
| F5.5 | 60-day UNCLAIMED boundary (frozen time) | PASS | `tests/test_unclaimed_boundary.py` |
| F6.1 | 3/item, 5 open, no self-claim, one approved per item | PASS | `tests/test_claim_limits.py` |
| F6.2 | Claimant never sees private answers; custodian sees both | PASS | `tests/test_claim_review.py`, scan tests |
| F6.3 | No auto-approval | PASS | code review of `app/claims/service.py` |
| F6.4 | Rejected counts toward limit | PASS | `tests/test_claim_limits.py` |
| F7.1 | Mobile + handover note only after approval | PASS | `tests/test_contact_reveal.py` |
| F7.2 | 7-day expiry back to open (frozen time) | PASS | `tests/test_claim_expiry.py` |
| F7.3 | Claimant can cancel | PASS | `tests/test_claim_review.py` |
| F7.4 | Both confirm → returned; one-sided does not | PASS | `tests/test_handover.py` |
| F7.5 | Marking returned deletes photos | PASS | `tests/test_photo_deletion.py` |
| F7.6 | Moderator custodian for office | PASS | `tests/test_handover.py` |
| F8.1 | Member CRUD lost reports | PASS | `tests/test_lost_reports.py` |
| F8.2 | Matching formula; no ML | PASS | `tests/test_matching.py`, `tests/test_matching_purity.py` |
| F8.3 | Suggestions visible only to finder + lost-report owner | PASS | `tests/test_matching_visibility.py` |
| F8.4 | Sensitive → category+place only | PASS | `tests/test_matching.py` |
| F8.5 | No web/db imports in matching module | PASS | `tests/test_matching_purity.py` |
| F9.1 | Report button on posts and claims; queue | PASS | `tests/test_moderation.py` |
| F9.2 | Hide / delete / suspend / edit; every action writes audit | PASS | `tests/test_moderation.py`, `tests/test_audit_rows.py` |
| F9.3 | Suspended user loses access next request | PASS | `tests/test_suspension.py` |
| F9.4 | Audit append-only | PASS | `tests/test_audit_rows.py::test_no_update_or_delete` |
| F10.1 | In-app notifications for new claim / approve / reject / match | PASS | `tests/test_notifications.py` |
| F10.2 | No item details in notification text | PASS | `tests/test_notifications.py::test_no_pii_in_text` |
| F10.3 | No TELEGRAM_BOT_TOKEN → UI hidden, code path unreachable | PASS | `tests/test_telegram.py` |
| F10.4 | Webhook secret; no double-send | PASS | `tests/test_telegram.py` |
| F10.5 | Telegram message is generic | PASS | `tests/test_telegram.py` |
| F11.1 | GET /health → 200 JSON | PASS | `tests/test_health.py` |
| F11.2 | Security headers on every response | PASS | `tests/test_security_headers.py` |
| F11.3 | Custom 404 / 500 pages | PASS | `app/main.py::not_found`, `server_error` |
| F11.4 | purge: 90-day window; frozen time | PASS | `tests/test_purge.py` |
| F11.5 | delete-my-data: posts/claims/photos/notifications; name → deleted-user | PASS | `tests/test_delete_my_data.py` |
| F11.6 | en.json and bn.json identical keys | PASS | `tests/test_bangla_ui.py`, `tests/test_i18n_keys.py` |
| F11.7 | DEMO_MODE banner; seed-demo idempotent | PASS | `tests/test_demo_seed.py` |
| F11.8 | No private answer / mobile / token / name in any log line | PASS | `tests/test_log_capture.py` |
| G.1 | docker compose up serves the app; fresh clone from README | PASS | `scripts/fresh_clone.sh` |
| G.2 | CI green on PostgreSQL | PASS | `.github/workflows/ci.yml` |
| G.3 | Full test suite passes locally | PASS | `171 passed, 1 skipped` |

## Test counts

- 171 unit/integration tests
- 1 E2E happy-path test
- 1 skipped (xdist-only)
- All lint clean (`ruff check .`)

## Stack

Python 3.12, FastAPI 0.115, SQLModel 0.0.22, Alembic 1.13.3, Jinja2 3.1,
argon2-cffi 23.1, Pillow 10.4, pytest 8.3, ruff 0.6.8, vendored HTMX 1.9.

## No scope creep

- No extra endpoints, models or features beyond SCOPE.md
- No new dependencies outside the ALLOWED STACK
- No refactoring outside the current milestone
