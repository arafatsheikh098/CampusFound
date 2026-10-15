"""Capture screenshots of the running CampusFound app for the README.

Run after:
    .venv/bin/alembic upgrade head
    .venv/bin/python -m app.cli seed-demo
    .venv/bin/python -m uvicorn app.main:app --port 8000

This script logs in as the demo moderator and a demo member, then captures
key pages. Re-run any time the UI changes.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

# Moderator from seed-demo: +8801711111111 / modpass12
MOD_MOBILE = "+8801711111111"
MOD_PASSWORD = "modpass12"
# One of the demo members: +8801722222222 / memberpass1
MEMBER_MOBILE = "+8801722222222"
MEMBER_PASSWORD = "memberpass1"


async def login(page, identifier: str, password: str) -> None:
    await page.goto(f"{BASE}/login", wait_until="networkidle")
    await page.fill('input[name="identifier"]', identifier)
    await page.fill('input[name="password"]', password)
    # Submit the form by pressing Enter inside the password field to avoid
    # language-switcher submit buttons that share the selector.
    await page.locator('input[name="password"]').press("Enter")
    await page.wait_for_load_state("networkidle")


async def shot(page, name: str) -> None:
    target = OUT / f"{name}.png"
    await page.screenshot(path=str(target), full_page=True)
    print(f"  -> {target.relative_to(OUT.parent.parent)}")


async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = await context.new_page()

        # Public pages (logged out)
        print("Public pages:")
        await page.goto(f"{BASE}/", wait_until="networkidle")
        await shot(page, "01-landing")

        await page.goto(f"{BASE}/login", wait_until="networkidle")
        await shot(page, "02-login")

        await page.goto(f"{BASE}/signup", wait_until="networkidle")
        await shot(page, "03-signup")

        # Browse items as a member
        print("Member flow:")
        await login(page, MEMBER_MOBILE, MEMBER_PASSWORD)
        await page.goto(f"{BASE}/items", wait_until="networkidle")
        await shot(page, "04-browse-items")

        # Try to find an item detail page
        all_item_links = await page.locator(
            'a[href^="/items/"]:not([href="/items/new"])'
        ).all()
        item_hrefs = []
        for link in all_item_links:
            href = await link.get_attribute("href")
            if href and href not in item_hrefs:
                item_hrefs.append(href)

        if item_hrefs:
            await page.goto(f"{BASE}{item_hrefs[0]}", wait_until="networkidle")
            await shot(page, "05-item-detail")

            # The first item is posted by this member (no claim link).
            # Visit the second one to capture a real claim form.
            if len(item_hrefs) > 1:
                await page.goto(f"{BASE}{item_hrefs[1]}", wait_until="networkidle")
                await shot(page, "05b-item-detail-claimable")
                claim_link = page.locator('a[href*="/claim"]').first
                if await claim_link.count():
                    claim_href = await claim_link.get_attribute("href")
                    if claim_href:
                        await page.goto(f"{BASE}{claim_href}", wait_until="networkidle")
                        await shot(page, "06-claim-form")

        # Lost report
        await page.goto(f"{BASE}/lost/new", wait_until="networkidle")
        await shot(page, "07-lost-report")

        await page.goto(f"{BASE}/notifications", wait_until="networkidle")
        await shot(page, "08-notifications")

        # Logout
        await page.goto(f"{BASE}/logout", wait_until="networkidle")

        # Moderator dashboard
        print("Moderator flow:")
        await login(page, MOD_MOBILE, MOD_PASSWORD)
        await page.goto(f"{BASE}/moderation", wait_until="networkidle")
        await shot(page, "09-moderation-dashboard")

        await page.goto(f"{BASE}/moderation/users", wait_until="networkidle")
        await shot(page, "10-moderation-users")

        # Bangla UI - language is set via a POST + cookie, then captured
        print("Bangla UI:")
        await page.context.add_cookies(
            [{"name": "lang", "value": "bn", "url": BASE}]
        )
        await page.goto(f"{BASE}/", wait_until="networkidle")
        await shot(page, "11-landing-bangla")

        await page.goto(f"{BASE}/items", wait_until="networkidle")
        await shot(page, "12-browse-items-bangla")

        await browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
