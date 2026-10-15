# Screenshots

PNG snapshots of the running app, used by the top-level `README.md` and any
docs/handouts. Files are kept in this folder so the repo root stays clean.

## Files

| File | What it shows | How it's produced |
| --- | --- | --- |
| `01-landing.png` | Public landing page, anonymous visitor | Script |
| `02-login.png` | Login form (identifier + password) | Script |
| `03-signup.png` | Signup form (full name, BD mobile, password) | Script |
| `04-browse-items.png` | Member view of `/items` with search/filters | Script |
| `05-item-detail.png` | Item detail page when the viewer is the finder | Script |
| `05b-item-detail-claimable.png` | Item detail page for a non-finder (claim CTA visible) | Script |
| `06-claim-form.png` | "Claim this item" form (verification question + note) | Script |
| `07-lost-report.png` | "Post a lost report" form | Script |
| `08-notifications.png` | In-app notifications page | Script |
| `09-moderation-dashboard.png` | Moderator dashboard (pending users, suspended, reports) | Script |
| `10-moderation-users.png` | Moderator user-management screen | Script |
| `11-landing-bangla.png` | Landing page in Bangla (`lang=bn`) | Script |
| `12-browse-items-bangla.png` | Browse items in Bangla | Script |

## Regenerating

The screenshots are produced by `scripts/capture_screenshots.py` using
Playwright. Re-run it any time the UI changes.

Prerequisites (one-time):

```bash
.venv/bin/pip install playwright
.venv/bin/python -m playwright install chromium-headless-shell
```

Then, in two terminals:

```bash
# Terminal 1
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli seed-demo
.venv/bin/python -m uvicorn app.main:app --port 8000
```

```bash
# Terminal 2
.venv/bin/python scripts/capture_screenshots.py
```

The script logs in as the demo moderator (`+8801711111111` / `modpass12`) and
a demo member (`+8801722222222` / `memberpass1`). If you change those
credentials in `app/cli.py`, update `MEMBER_*` / `MOD_*` constants in the
script too.

## Adding a new screenshot

1. Add a new `await shot(page, "13-your-name")` call in the appropriate
   section of `capture_screenshots.py` (public / member / moderator / Bangla).
2. Re-run the script.
3. Add a row to the table above.
4. Reference it from `README.md` with
   `![Caption](docs/screenshots/13-your-name.png)`.
