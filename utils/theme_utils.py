"""Theme utilities for the WNBA Predictions app.

The theme is chosen automatically from the browser's local time:
- Daytime (6 AM - 6 PM): Lilac Dawn
- Nighttime (6 PM - 6 AM): Wine Violet

Streamlit loads theme colors from .streamlit/config.toml at startup. To apply
the time-based theme, we write the chosen theme to that file and rerun.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.themes import ALL_THEMES, get_theme  # noqa: E402

CONFIG_PATH = ROOT / ".streamlit" / "config.toml"

# Theme chosen by time of day (browser-local)
DAYTIME_THEME = "lilac_dawn"
NIGHTTIME_THEME = "wine_violet"
DAYTIME_START_HOUR = 6   # 6 AM
NIGHTTIME_START_HOUR = 18  # 6 PM

VALID_THEME_KEYS = [
    "primaryColor",
    "backgroundColor",
    "secondaryBackgroundColor",
    "textColor",
    "font",
]


def theme_for_hour(hour: int) -> str:
    """Return the theme slug for a given hour (0-23, browser-local)."""
    if DAYTIME_START_HOUR <= hour < NIGHTTIME_START_HOUR:
        return DAYTIME_THEME
    return NIGHTTIME_THEME


def browser_hour() -> int:
    """Return the browser-local hour (0-23) using st.context timezone info.

    Falls back to server-local time when the browser timezone isn't reported
    (e.g. the first render of a session, or non-browser clients).
    """
    import streamlit as st

    tz = st.context.timezone
    if tz:
        try:
            # st.context.timezone is an IANA name like "America/New_York".
            from zoneinfo import ZoneInfo

            return datetime.now(timezone.utc).astimezone(ZoneInfo(tz)).hour
        except Exception:
            pass
    offset = st.context.timezone_offset
    if offset is not None:
        try:
            # offset is in minutes east of UTC (browser's Date.getTimezoneOffset is reversed).
            browser_now = datetime.now(timezone.utc) + timedelta(minutes=-int(offset))
            return browser_now.hour
        except (TypeError, ValueError):
            pass
    return datetime.now().hour


def apply_theme(slug: str) -> None:
    """Write the theme for *slug* into .streamlit/config.toml (preserving other sections).

    Only the valid Streamlit [theme] keys are written (name/description are
    display metadata, not config).
    """
    theme = get_theme(slug)
    text = CONFIG_PATH.read_text(encoding="utf-8")
    theme_block = "[theme]\n" + "\n".join(
        f'{k} = "{theme[k]}"' for k in VALID_THEME_KEYS
    )
    # Replace the existing [theme] section (everything between [theme] and the
    # next section header), or append at the top if none exists.
    if "[theme]" in text:
        new_text = re.sub(
            r"\[theme\].*?(?=\n\[|\Z)",
            theme_block,
            text,
            count=1,
            flags=re.DOTALL,
        )
    else:
        new_text = theme_block + "\n\n" + text
    CONFIG_PATH.write_text(new_text, encoding="utf-8")


def current_theme_slug() -> str:
    """Read the theme colors from config.toml to detect the active theme.

    Compares the full color set (primary + background + secondary + text) since
    multiple themes share the same primaryColor (e.g. #D6286A is used by
    Graphite Ice, Peach Fizz, Buttercream, and Wine Violet).
    """
    text = CONFIG_PATH.read_text(encoding="utf-8")

    def _val(key: str) -> str:
        m = re.search(rf'^{key}\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
        return m.group(1) if m else ""

    active = {
        "primaryColor": _val("primaryColor"),
        "backgroundColor": _val("backgroundColor"),
        "secondaryBackgroundColor": _val("secondaryBackgroundColor"),
        "textColor": _val("textColor"),
    }
    for slug, theme in ALL_THEMES.items():
        if all(theme[k] == active.get(k) for k in active):
            return slug
    return "brand"


def ensure_time_based_theme() -> str:
    """Apply the theme matching the browser-local hour if it differs from the active one.

    Returns the slug now in effect.
    """
    desired = theme_for_hour(browser_hour())
    current = current_theme_slug()
    if desired != current:
        apply_theme(desired)
    return desired

