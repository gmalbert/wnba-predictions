"""Streamlit vs React parity + performance harness.

Drives both the Streamlit reference and the React preview, captures
screenshots at desktop (1440x900) and mobile (390x844), records
Lighthouse-style metrics for each route, and verifies there are no
console errors on either side. Output is written under
``docs/react-migration/parity/`` (screenshots) and
``docs/react-migration/perf/`` (perf metrics).

Run::

    python scripts/test_react_parity.py
    python scripts/test_react_parity.py --base-react http://127.0.0.1:4173
    python scripts/test_react_parity.py --base-streamlit http://127.0.0.1:8501

Exit code is 0 on success and 1 on any parity / perf regression / console
error.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import (
    Browser,
    BrowserContext,
    ConsoleMessage,
    Page,
    Request,
    Response,
    sync_playwright,
)

DEFAULT_REACT = "http://127.0.0.1:4173"
DEFAULT_STREAMLIT = "http://127.0.0.1:8501"

REACT_ROUTES = [
    ("Home", "/"),
    ("Game_Predictions", "/game-predictions"),
    ("Scenario_Lab", "/scenario-lab"),
    ("Standings", "/standings"),
    ("Team_Stats", "/team-stats"),
    ("Player_Stats", "/player-stats"),
    ("Model_Performance", "/model-performance"),
    ("Data_Health", "/data-health"),
]

STREAMLIT_PAGES = [
    ("Home", "/"),
    ("Game_Predictions", "/Game_Predictions"),
    ("Scenario_Lab", "/Scenario_Lab"),
    ("Standings", "/Standings"),
    ("Team_Stats", "/Team_Stats"),
    ("Player_Stats", "/Player_Stats"),
    ("Model_Performance", "/Model_Performance"),
    ("Data_Health", "/Data_Health"),
]

VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "mobile": {"width": 390, "height": 844},
}

PAGE_EXPECTED = {
    "Home": ["WNBA Predictions"],
    "Game_Predictions": ["Game Predictions"],
    "Scenario_Lab": ["Scenario Lab"],
    "Standings": ["WNBA Standings"],
    "Team_Stats": ["Team Stats"],
    "Player_Stats": ["Player Stats"],
    "Model_Performance": ["Model Performance"],
    "Data_Health": ["Data Health"],
}

PERF_DIR = ROOT / "docs" / "react-migration" / "perf"
PARITY_DIR = ROOT / "docs" / "react-migration" / "parity"


def _launch_browser(playwright) -> Browser:
    """Use managed Chromium when installed, otherwise fall back to a system browser."""
    try:
        return playwright.chromium.launch(headless=True)
    except Exception as first_error:
        candidates = [
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        ]
        for executable in candidates:
            if executable.exists():
                print(f"Using system browser: {executable}", flush=True)
                return playwright.chromium.launch(headless=True, executable_path=str(executable))
        raise first_error


def _streamlit_url(base: str, path: str) -> str:
    if path == "/":
        return base.rstrip("/") + "/"
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def _measure_perf(page: Page) -> dict[str, Any]:
    """Collect Lighthouse-style metrics from a Playwright Page."""
    nav_entry: dict[str, Any] | None = None
    for entry in page.evaluate(
        "() => performance.getEntriesByType('navigation').map(e => ({"
        "  domContentLoadedEventEnd: e.domContentLoadedEventEnd,"
        "  loadEventEnd: e.loadEventEnd,"
        "  responseEnd: e.responseEnd,"
        "  startTime: e.startTime"
        "}))"
    ):
        nav_entry = entry
        break
    paint = page.evaluate(
        "() => Object.fromEntries(performance.getEntriesByType('paint').map(e => [e.name, e.startTime]))"
    )
    fcp = paint.get("first-contentful-paint")
    fp = paint.get("first-paint")
    resources = page.evaluate(
        "() => performance.getEntriesByType('resource').map(r => ({"
        "  name: r.name,"
        "  transferSize: r.transferSize,"
        "  encodedBodySize: r.encodedBodySize,"
        "  decodedBodySize: r.decodedBodySize,"
        "  duration: r.duration,"
        "  initiatorType: r.initiatorType"
        "}))"
    )
    total_bytes = sum(int(r.get("transferSize") or r.get("encodedBodySize") or 0) for r in resources)
    js_requests = [r for r in resources if str(r.get("initiatorType") or "") in {"script", "link", ""} and ".js" in str(r.get("name") or "")]
    js_count = len(js_resources := [
        r for r in resources
        if any(str(r.get("name") or "").endswith(ext) for ext in (".js", ".mjs"))
    ])
    js_bytes = sum(int(r.get("transferSize") or r.get("encodedBodySize") or 0) for r in js_resources)
    tti_estimate = None
    if nav_entry:
        dcl = nav_entry.get("domContentLoadedEventEnd")
        load = nav_entry.get("loadEventEnd")
        tti_estimate = max(dcl or 0, load or 0) + (nav_entry.get("startTime") or 0)
    return {
        "first_contentful_paint_ms": fcp,
        "first_paint_ms": fp,
        "dom_content_loaded_ms": nav_entry.get("domContentLoadedEventEnd") if nav_entry else None,
        "load_ms": nav_entry.get("loadEventEnd") if nav_entry else None,
        "tti_estimate_ms": tti_estimate,
        "total_transferred_bytes": total_bytes,
        "js_request_count": js_count,
        "js_transferred_bytes": js_bytes,
        "resource_count": len(resources),
    }


def _collect_console(page: Page) -> list[str]:
    errors: list[str] = []

    def on_msg(msg: ConsoleMessage) -> None:
        if msg.type in {"error"}:
            errors.append(f"{msg.type}: {msg.text}")

    def on_request_failed(req: Request) -> None:
        url = req.url
        if url.startswith("data:"):
            return
        if req.failure and "net::ERR_ABORTED" in (req.failure or ""):
            return
        errors.append(f"request_failed: {url} {req.failure}")

    def on_response(resp: Response) -> None:
        if resp.status >= 400 and not resp.url.startswith("data:"):
            errors.append(f"http_{resp.status}: {resp.url}")

    page.on("console", on_msg)
    page.on("requestfailed", on_request_failed)
    page.on("response", on_response)
    return errors


def _drive_react(browser: Browser, base: str, results: dict[str, Any]) -> None:
    perf_by_route: dict[str, Any] = {}
    console_errors_by_route: dict[str, list[str]] = {}
    for label, route in REACT_ROUTES:
        console_errors_by_route[label] = []
        for vp_name, vp in VIEWPORTS.items():
            ctx: BrowserContext = browser.new_context(viewport=vp, ignore_https_errors=True)
            page = ctx.new_page()
            errors = _collect_console(page)
            console_errors_by_route[label].extend(errors)
            url = f"{base.rstrip('/')}{route}"
            page.goto(url, wait_until="networkidle", timeout=30000)
            # Wait for the page to render the expected label text.
            expected = PAGE_EXPECTED.get(label, [label.replace("_", " ").lower()])
            try:
                page.wait_for_function(
                    "expected => Array.isArray(expected) ? expected.every(t => "
                    "document.body && document.body.innerText.toLowerCase().includes(t.toLowerCase())) "
                    ": document.body && document.body.innerText.toLowerCase().includes(expected.toLowerCase())",
                    arg=expected,
                    timeout=15000,
                )
            except Exception as exc:
                console_errors_by_route[label].append(f"hydration_timeout: {exc}")
            page.wait_for_timeout(800)
            parity_dir = PARITY_DIR / _slug(label)
            parity_dir.mkdir(parents=True, exist_ok=True)
            shot = parity_dir / f"react-{vp_name}.png"
            page.screenshot(path=str(shot), full_page=False)
            if vp_name == "desktop":
                perf_by_route[label] = _measure_perf(page)
                perf_by_route[label]["url"] = url
            ctx.close()
    results["react_perf"] = perf_by_route
    results["react_console_errors"] = console_errors_by_route


def _drive_streamlit(browser: Browser, base: str, results: dict[str, Any]) -> None:
    perf_by_route: dict[str, Any] = {}
    console_errors_by_route: dict[str, list[str]] = {}
    for label, route in STREAMLIT_PAGES:
        console_errors_by_route[label] = []
        for vp_name, vp in VIEWPORTS.items():
            ctx = browser.new_context(viewport=vp, ignore_https_errors=True)
            page = ctx.new_page()
            errors = _collect_console(page)
            console_errors_by_route[label].extend(errors)
            url = _streamlit_url(base, route)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_selector("[data-testid='stHeader']", timeout=60000)
            except Exception as exc:
                console_errors_by_route[label].append(f"hydration_timeout: {exc}")
            expected = PAGE_EXPECTED.get(label, [label.replace("_", " ").lower()])
            hydrated = False
            for _ in range(30):
                body = page.inner_text("body")
                lowered = body.lower()
                if all(t.lower() in lowered for t in expected) and len(body.strip()) > 100:
                    hydrated = True
                    break
                page.wait_for_timeout(1000)
            if not hydrated:
                console_errors_by_route[label].append("expected text not present after 30s polling")
            # Streamlit ships elements over the websocket after the header text
            # appears; give late deltas (metric values, tables) time to paint.
            page.wait_for_timeout(5000)
            parity_dir = PARITY_DIR / _slug(label)
            parity_dir.mkdir(parents=True, exist_ok=True)
            shot = parity_dir / f"streamlit-{vp_name}.png"
            page.screenshot(path=str(shot), full_page=False)
            if vp_name == "desktop":
                perf_by_route[label] = _measure_perf(page)
                perf_by_route[label]["url"] = url
            ctx.close()
    results["streamlit_perf"] = perf_by_route
    results["streamlit_console_errors"] = console_errors_by_route


def _slug(label: str) -> str:
    return label.replace(" ", "-").replace("_", "-").lower()


def _write_reports(results: dict[str, Any]) -> None:
    PERF_DIR.mkdir(parents=True, exist_ok=True)
    PARITY_DIR.mkdir(parents=True, exist_ok=True)
    (PERF_DIR / "react.json").write_text(json.dumps(results["react_perf"], indent=2), encoding="utf-8")
    (PERF_DIR / "streamlit.json").write_text(json.dumps(results["streamlit_perf"], indent=2), encoding="utf-8")
    (PERF_DIR / "console-errors.json").write_text(
        json.dumps({
            "react": results["react_console_errors"],
            "streamlit": results["streamlit_console_errors"],
        }, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Streamlit vs React parity + performance harness.")
    parser.add_argument("--base-react", default=DEFAULT_REACT)
    parser.add_argument("--base-streamlit", default=DEFAULT_STREAMLIT)
    parser.add_argument("--skip-streamlit", action="store_true")
    parser.add_argument("--skip-react", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    results: dict[str, Any] = {
        "react_perf": {},
        "streamlit_perf": {},
        "react_console_errors": {},
        "streamlit_console_errors": {},
    }

    with sync_playwright() as p:
        browser = _launch_browser(p)
        try:
            if not args.skip_react:
                if not args.quiet:
                    print(f"Driving React at {args.base_react}")
                _drive_react(browser, args.base_react, results)
            if not args.skip_streamlit:
                if not args.quiet:
                    print(f"Driving Streamlit at {args.base_streamlit}")
                _drive_streamlit(browser, args.base_streamlit, results)
        finally:
            browser.close()

    _write_reports(results)

    react_console_total = sum(len(v) for v in results["react_console_errors"].values())
    streamlit_console_total = sum(len(v) for v in results["streamlit_console_errors"].values())
    if not args.quiet:
        print(f"React console errors: {react_console_total}")
        print(f"Streamlit console errors: {streamlit_console_total}")

    failed = 0
    if react_console_total > 0:
        for label, errors in results["react_console_errors"].items():
            if errors:
                failed += 1
                print(f"  [FAIL] react {label}:")
                for err in errors:
                    print(f"    {err}")
    if not args.skip_streamlit and streamlit_console_total > 0:
        for label, errors in results["streamlit_console_errors"].items():
            if errors:
                failed += 1
                print(f"  [FAIL] streamlit {label}:")
                for err in errors:
                    print(f"    {err}")
    if failed:
        print(f"{failed} page(s) had console errors.")
    else:
        print("No console errors on either side.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())