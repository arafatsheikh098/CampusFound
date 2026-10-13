# SCOPE.md — locked contract (do not edit)

This file is the contract. Implementation must satisfy the acceptance criteria. Any change to IN SCOPE, OUT OF SCOPE, ALLOWED STACK, or ACCEPTANCE CRITERIA must be made by the user, never by the agent.

## IN SCOPE
F1 Accounts with moderator approval: sign-up form (full name, department, batch or session, mobile number, password, checkbox "I am a student or staff member of this campus", checkbox "I am 18 or older"). New accounts are pending until a moderator approves them after checking the person through the department or in person; rejected or suspended accounts cannot log in. Passwords use argon2-cffi; signed session cookie (HttpOnly, SameSite=Lax, Secure in production); CSRF on every state-changing request; login rate limit in the database; single-use recovery codes (10, shown once, stored hashed) instead of email reset; moderators are created by CLI. Mobile numbers are validated and normalized (Bangladesh format +8801XXXXXXXXX).
F2 Locations and categories: moderator-managed list of campus places (for example library, a department building, a hall) and categories. Sensitive categories (ID card, bank or payment card, passport or official document, SIM or phone) are flagged: posts in them cannot have photos and show only a generic description; the finder is told to hand the item to the office, and the post is created with custody "office".
F3 Found-item posts: category, place found, date found (not in the future, at most 60 days ago), public description (max 300, with guidance: do not describe unique hidden marks), up to 2 photos (not allowed for sensitive categories), custody (finder holds it, or office), preferred handover note (max 150, for example "Library desk, 10:00 to 13:00"), and 1 to 3 verification questions (each max 120) with the finder's private answers (each max 120). Private answers are visible only to the finder and moderators and are never shown to claimants.
F4 Photo safety: size cap (5 MB), content-type validated by decoding (not by extension), pixel cap, EXIF and all metadata stripped, re-encoded to WebP or JPEG, downscaled to at most 1024 px on the long side, stored in the database as bytes, served only to approved members through an authenticated endpoint with Cache-Control private and Content-Disposition inline and X-Content-Type-Options nosniff. Uploads that are not decodable images are rejected with a clear error.
F5 Browse and search (members only): list and search found items by category, place, date range and keywords (title and description); items in sensitive categories show generic text only; pagination; items older than 60 days without a claim move to "unclaimed at office" for moderator handling.
F6 Claims: a member opens a claim on a found item by answering the verification questions in free text (each answer max 200) and a short note. Limits: at most 3 claim attempts per member per item, at most 5 open claims per member, a claim cannot be made on your own post, and only one claim can be in "approved, awaiting handover" at a time per item. The custodian (finder, or a moderator for office items) sees the claimant's answers side by side with the private answers and approves or rejects with a short reason. Matching is always a human decision; the system never auto-approves. Rejected claims count toward the attempt limit.
F7 Handover and contact: contact details are revealed only after approval and only between the custodian and the approved claimant (mobile number and the handover note). Handover completes when both confirm "returned" (or a moderator confirms for office items); then the item is marked returned and its photos are deleted. A claimant can cancel; an approved claim that is not handed over within 7 days expires back to open (configurable).
F8 Lost reports: a member can post a lost-item report (category, place, date lost, description, optional private note). When a found item is posted, the app computes simple keyword and category matches against open lost reports (same category required; score from shared keywords, place and date window; no machine learning) and shows possible matches to the finder and to the owner of the lost report, inside the app only. A match is a suggestion; the owner still has to make a claim.
F9 Moderation and safety: report button on posts and claims with a reason; moderator queues for pending accounts, reports and disputes; moderators can hide or delete posts, suspend accounts, and edit categories and places; every moderator action and every approval, rejection, reveal and handover is written to an audit log; suspended users lose access immediately.
F10 Notifications: in-app notification list with unread count (new claim on your post, claim approved or rejected, possible match); optional Telegram notifications when TELEGRAM_BOT_TOKEN is set, linked by a one-time code, secret-token-authenticated webhook, generic message text (never item details, answers, names or numbers), all disabled cleanly when unset.
F11 Privacy and operations: data minimization (no student ID numbers, no addresses, no precise GPS); returned and old items are purged on a schedule (`python -m app.cli purge`, default 90 days after return or expiry); delete-my-data; English and Bangla UI with identical dictionary keys; GET /health; security headers (CSP without inline scripts, X-Content-Type-Options, Referrer-Policy, frame-ancestors none); custom 404/500 pages; DEMO_MODE with a banner and fake data; idempotent demo seed.

## OUT OF SCOPE
Public (logged-out) browsing of items, payments or rewards, shipping or courier, face recognition or any image matching, machine-learning matching, email, SMS, chat between users, maps or GPS, multiple campuses, anything not listed above.

## ALLOWED STACK
Python 3.12; FastAPI; uvicorn; SQLModel; Alembic; psycopg[binary]; pydantic-settings; Jinja2; python-multipart; argon2-cffi; Pillow; httpx (Telegram Bot API only); vendored HTMX (eval disabled); pytest, pytest-playwright, httpx, freezegun, hypothesis; ruff; Docker, docker compose; GitHub Actions.

## ACCEPTANCE CRITERIA
Every feature has a numbered, testable check.

### F1 Accounts
1. A new user can submit the sign-up form; the account is stored with status `pending`; login is blocked with a clear "awaiting approval" message until a moderator approves it.
2. Passwords are stored using argon2-cffi; a unit test verifies the hash format starts with `$argon2`.
3. A login failure increments a per-username counter in the database; the 6th failure within 15 minutes returns 429; the counter is reset on success; `freezegun` controls time.
4. The login response is the same generic "invalid credentials" for both unknown username and wrong password (single code path).
5. Recovery codes: 10 codes generated on first login, shown once, stored hashed; each code works exactly once; after use the code row is removed.
6. A moderator can be created only by a CLI command `python -m app.cli create-moderator ...`; the form cannot create a moderator.
7. Production refuses to start if `SECRET_KEY` equals the development default.
8. Pending, rejected and suspended accounts cannot log in; suspended accounts' existing sessions stop working immediately (next request returns 401/redirect).

### F2 Locations and categories
1. A moderator can add, rename and delete a place and a category; non-moderators get 403 on these routes.
2. A category has a `sensitive` boolean; a non-moderator cannot toggle it through the public form.
3. A post in a sensitive category forces custody `office`; the post is created even if the form said `finder` (server-side enforcement).

### F3 Found-item posts
1. `date_found` cannot be in the future and cannot be older than 60 days (boundary tests with frozen time).
2. `description` is at most 300 chars; HTML characters are escaped on render.
3. Between 1 and 3 verification questions, each at most 120 chars; each private answer at most 120 chars.
4. `handover_note` is at most 150 chars.
5. Posts in sensitive categories cannot have photos (server ignores any uploaded photo bytes; DB has zero photo rows for that post).
6. Private answers are stored but never rendered on any page accessible to non-owner, non-moderator users (scan tests).
7. Only the post owner or a moderator can edit or withdraw a post.

### F4 Photo pipeline
1. An image with GPS EXIF data, when uploaded, is stored without that metadata (test inspects bytes; `PIL.Image.open(BytesIO(bytes))._getexif()` is None).
2. The following uploads are rejected with a clear error: a text file renamed .jpg, a truncated JPEG, an image above the pixel cap (decompression bomb), a file over 5 MB, an SVG, a polyglot file (valid image bytes with appended script), an empty file.
3. The photo serving endpoint returns 404 to logged-out, pending and suspended users and sets `Cache-Control: private`, `X-Content-Type-Options: nosniff`, `Content-Disposition: inline`.
4. At most 2 photos per post; sensitive categories can never have photos regardless of what the client sends.
5. Photos are deleted from the database when a post is withdrawn or returned (test counts rows before/after).
6. The stored image's long side is at most 1024 px after re-encoding.

### F5 Browse and search
1. Filters combine correctly (test matrix of category × place × date × keyword) and pagination boundaries (page 1, last page, beyond-last) are correct.
2. Keyword search is case-insensitive, handles Bangla text, treats SQL `%` and HTML `<` as plain text.
3. Sensitive items never reveal any field beyond the generic placeholder in list and search results.
4. Logged-out requests to a member item page return the login page (status 200) without leaking that the item exists (no item title or ID in body).
5. An item older than 60 days without a claim moves to "unclaimed at office" at the exact boundary (frozen time).

### F6 Claims
1. Limits enforced: 3 attempts per member per item; 5 open claims per member; no self-claim; one approved claim per item.
2. The claimant never sees the private answers; the custodian sees both sets side by side on the review screen.
3. Matching is always human: no code path auto-approves.
4. A rejected claim counts toward the attempt limit.

### F7 Handover and contact
1. Mobile numbers and the handover note are revealed only to the custodian and the approved claimant (G3 scan before and after approval).
2. An approved claim that is not handed over within 7 days expires back to open at the exact boundary (frozen time); the attempt limit is not reset.
3. A claimant can cancel an open or approved claim.
4. Both parties confirming `returned` marks the item returned; one-sided confirmation does not.
5. Marking returned deletes all photos for that item.
6. Moderators can act as custodian for office items.

### F8 Lost reports and matching
1. A member can CRUD their own lost reports.
2. When a found item is posted, the matching function returns suggestions with the documented formula: same category required, score from shared keywords (case-folded, no stop-word list), place match bonus, date-window proximity bonus; no ML, no DB access in the matching module.
3. Suggestions are visible only to the finder and the lost-report owner, never to other members.
4. Sensitive categories produce no keyword matching on item text; matching is by category and place only.
5. The matching function imports nothing from the web or database layers (test).

### F9 Moderation and safety
1. Any member can report a post or a claim with a free-text reason; reports appear in a moderator queue.
2. Moderators can hide a post, delete a post, suspend an account, edit categories and places; every action writes one audit row.
3. A suspended user loses access on the next request (test of session).
4. Audit log is append-only; tests confirm no UPDATE/DELETE on the table.

### F10 Notifications
1. In-app notifications are created for: new claim on your post, claim approved, claim rejected, possible match for your lost report.
2. Notification text contains no item details, answers, names or numbers (test scans the notification list).
3. With no `TELEGRAM_BOT_TOKEN` set, the Telegram UI is hidden and no Telegram code path is reachable.
4. The Telegram webhook rejects calls without the secret header; the same notification is not sent twice from a double-tap.
5. The Telegram message text is generic (no item text, no answer, no name, no number).

### F11 Privacy and operations
1. `GET /health` returns 200 JSON.
2. Security headers present on every response: `Content-Security-Policy` (no inline scripts, frame-ancestors none), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.
3. Custom 404 and 500 pages render.
4. `python -m app.cli purge` removes items 90 days after return or expiry, with their claims, photos and answers; leaves newer items untouched (frozen time).
5. `python -m app.cli delete-my-data <user_id>` removes that user's posts, claims, photos and notifications and replaces their name in audit rows with `deleted-user` (count test).
6. `en.json` and `bn.json` have identical keys (test diff).
7. `DEMO_MODE=1` shows a banner on every page; `python -m app.cli seed-demo` is idempotent (run twice, no duplicate users or posts).
8. No private answer, mobile number, token or name appears in any log line during tests (log-capture test).

### Global
1. `docker compose up --build` serves the app; the demo seed loads; a fresh clone works from the README only.
2. CI is green on PostgreSQL.
3. The full test suite passes locally and in CI.
