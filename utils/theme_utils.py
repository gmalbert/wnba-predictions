"""Theme switching utilities for the WNBA Predictions app.

Streamlit loads theme colors from .streamlit/config.toml at startup. To change
the theme live, we write the chosen theme back to that file and trigger a rerun
so Streamlit re-reads it. The sidebar selector in predictions.py calls these.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.themes import ALL_THEMES, get_theme  # noqa: E402

CONFIG_PATH = ROOT / ".streamlit" / "config.toml"


VALID_THEME_KEYS = [
    "primaryColor",
    "backgroundColor",
    "secondaryBackgroundColor",
    "textColor",
    "font",
]


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
        import re

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
    """Read the current primaryColor from config.toml to detect the active theme."""
    text = CONFIG_PATH.read_text(encoding="utf-8")
    for slug, theme in ALL_THEMES.items():
        if f'primaryColor = "{theme["primaryColor"]}"' in text:
            return slug
    return "brand"
