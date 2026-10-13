PROJECT: CampusFound
PURPOSE: Members of one campus post items they found or lost. An owner claims a found item by answering verification questions that only the real owner can answer. The finder (or a moderator) decides. The item is then handed over and marked returned. The system is designed to make false claims hard and to expose as little personal data as possible.

ROLES
- Member: an approved campus user who can post found items, post lost reports and make claims.
- Moderator: reviews account requests, handles reports and disputes, can act on any post or claim, and can act as custodian for items kept at the office.
- Public visitor: sees only a landing page and how it works.

IN SCOPE
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

OUT OF SCOPE
Public (logged-out) browsing of items, payments or rewards, shipping or courier, face recognition or any image matching, machine-learning matching, email, SMS, chat between users, maps or GPS, multiple campuses, anything not listed above.

ALLOWED STACK
Python 3.12; FastAPI; uvicorn; SQLModel; Alembic; psycopg[binary]; pydantic-settings; Jinja2; python-multipart; argon2-cffi; Pillow; httpx (Telegram Bot API only); vendored HTMX (eval disabled); pytest, pytest-playwright, httpx, freezegun, hypothesis; ruff; Docker, docker compose; GitHub Actions.

GLOBAL ACCEPTANCE CRITERIA
G1 docker compose up --build serves the app; the demo seed loads; a fresh clone works from the README.
G2 Private answers never appear in any response, page, notification, log or export visible to a claimant (tests scan every claimant-visible output for seeded private answers).
G3 Contact details (mobile numbers) never appear anywhere until a claim is approved, and then only for the two parties (tests).
G4 Pending, rejected and suspended users cannot access any member page or the photo endpoint.
G5 Uploaded images have all metadata removed, are re-encoded, and non-images, oversize files, decompression bombs and polyglot files are rejected (tests with crafted files).
G6 Claim limits (3 attempts per item per member, 5 open claims per member, no self-claims, one approved claim per item) hold, including under concurrent requests on Postgres.
G7 Sensitive categories can never have photos, whatever the client sends (tampered-input test).
G8 Every state-changing route rejects missing CSRF and missing session (route-discovery test).
G9 The English and Bangla dictionaries have identical keys.
G10 CI is green on PostgreSQL.

MILESTONES
M1 Foundation and i18n scaffold; M2 Accounts, moderator approval and security baseline; M3 Locations, categories and found-item posts; M4 Photo pipeline; M5 Browse and search; M6 Claims, decisions and handover; M7 Lost reports and matching; M8 Moderation, notifications and privacy operations; M9 Seed, Bangla UI and end-to-end tests.
