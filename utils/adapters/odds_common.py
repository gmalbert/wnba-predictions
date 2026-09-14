"""Shared helpers for odds-provider adapters."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pandas as pd

from utils.data_contracts import ODDS_COLUMNS


def now_utc() -> str:
    """Return a compact UTC timestamp for normalized observations."""
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def load_env_key(name: str) -> str:
    """Read a provider key from the environment or the repo's ignored .env."""
    key = os.getenv(name, "").strip()
    if key:
        return key
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def as_float(value: object) -> float | None:
    """Parse a numeric provider value, ignoring blanks and off-board sentinels."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed == 0.0001:
        return None
    return parsed


def to_american(value: object) -> int | None:
    """Normalize decimal or American odds to an American integer price."""
    parsed = as_float(value)
    if parsed is None or parsed == 0:
        return None
    # Odds-API.io returns decimal prices; TheRundown returns American prices.
    if 1.0 < parsed < 20.0:
        american = (parsed - 1.0) * 100.0 if parsed >= 2.0 else -100.0 / (parsed - 1.0)
        return int(round(american))
    return int(round(parsed))


def numeric_point(value: object) -> float | None:
    parsed = as_float(value)
    return round(parsed, 4) if parsed is not None else None


def empty_odds() -> pd.DataFrame:
    return pd.DataFrame(columns=ODDS_COLUMNS)

