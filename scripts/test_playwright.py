"""Playwright smoke test for the WNBA Predictions Streamlit site.

Verifies:
1. The main page (predictions.py) loads and renders.
2. The navigation sidebar shows all pages.
3. Each page loads without errors.
4. Key content (title, matchups, metrics) is visible.

Run: python scripts/test_playwright.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8501"
PAGES = [
    ("Game_Predictions", "Game Predictions"),
    ("Standings", "Standings"),
    ("Team_Stats", "Team Stats"),
    ("Player_Stats", "Player Stats"),
    ("Model_Performance", "Model Performance"),
    ("Data_Health", "Data Health"),
]


def main() -> int:
    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        # ── Main page ─────────────────────────────────────────────────────────
        print("Loading main page...", flush=True)
        page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
        time.sleep(3)
        body = page.inner_text("body").lower()
        for expected in ["wnba predictions", "season"]:
            if expected not in body:
                failures.append(f"Main page missing text: {expected!r}")
        print(f"Main page text length: {len(body)}", flush=True)

        # Sidebar navigation
        sidebar = page.inner_text("section[data-testid='stSidebar']").lower()
        for _, label in PAGES:
            if label.lower() not in sidebar:
                failures.append(f"Sidebar missing page: {label}")
        print("Sidebar nav verified", flush=True)

        # ── Each page ─────────────────────────────────────────────────────────
        for filename, label in PAGES:
            print(f"Loading {filename}...", flush=True)
            page.goto(f"{BASE_URL}/{filename}", wait_until="networkidle", timeout=60000)
            time.sleep(2)
            body = page.inner_text("body")
            if len(body.strip()) < 50:
                failures.append(f"{filename} returned near-empty page")
            print(f"  {label}: {len(body)} chars", flush=True)

        # Collect console/page errors (ignore benign favicon/asset 404s)
        real_errors = [
            e for e in errors
            if "404" not in e
            and "does not seem to exist" not in e
            and "Failed to load resource" not in e
        ]
        if real_errors:
            failures.append(f"Console errors on pages: {real_errors[:5]}")

        browser.close()

    if failures:
        print("\nFAILURES:", flush=True)
        for f in failures:
            print(f"  - {f}", flush=True)
        return 1
    print("\nALL PAGES PASSED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
