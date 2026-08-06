"""Canonical team and player identity resolution.

Maps source-specific IDs (WNBA Stats, ESPN, BALLDONTLIE, Basketball Reference,
wehoop) to stable canonical IDs. Seeded by scripts/bootstrap_reference_data.py
and enriched/validated by scripts/normalize_raw_data.py.

Unmatched identities are *reported*, never silently dropped: the helper
functions here return None for unknown inputs and callers are expected to
surface the miss in a data-health report.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from utils.league_config import get_league_config


def reference_dir() -> Path:
    cfg = get_league_config()
    return cfg.storage_namespace("reference")


def teams_path() -> Path:
    return reference_dir() / "teams.parquet"


def players_path() -> Path:
    return reference_dir() / "players.parquet"


def load_teams() -> pd.DataFrame:
    """Load the canonical teams reference table (empty frame if missing)."""
    p = teams_path()
    if p.exists():
        try:
            return pd.read_parquet(p)
        except Exception:
            pass
    return pd.DataFrame()


def load_players() -> pd.DataFrame:
    """Load the canonical players reference table (empty frame if missing)."""
    p = players_path()
    if p.exists():
        try:
            return pd.read_parquet(p)
        except Exception:
            pass
    return pd.DataFrame()


# ── Team identity ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _team_lookups() -> dict[str, dict]:
    """Build {source_field: {value: row_dict}} lookups from the teams table."""
    df = load_teams()
    lookups: dict[str, dict] = {}
    if df.empty:
        return lookups
    for field in [
        "canonical_team_id",
        "wnba_stats_team_id",
        "espn_team_id",
        "balldontlie_team_id",
        "basketball_reference_slug",
        "wehoop_team_id",
    ]:
        if field not in df.columns:
            continue
        lookups[field] = {
            str(r.get(field)): r
            for r in df.to_dict("records")
            if pd.notna(r.get(field)) and str(r.get(field))
        }
    return lookups


def get_team(source: str, source_id) -> Optional[dict]:
    """Resolve a team row from a source field + id. Returns None if unknown."""
    field_map = {
        "wnba_stats": "wnba_stats_team_id",
        "espn": "espn_team_id",
        "balldontlie": "balldontlie_team_id",
        "basketball_reference": "basketball_reference_slug",
        "wehoop": "wehoop_team_id",
    }
    field = field_map.get(source)
    if not field or source_id is None:
        return None
    lookups = _team_lookups()
    return lookups.get(field, {}).get(str(source_id))


def get_team_by_canonical(canonical_id) -> Optional[dict]:
    lookups = _team_lookups()
    return lookups.get("canonical_team_id", {}).get(str(canonical_id))


def get_team_id(source: str, source_id) -> Optional[int]:
    """Return the canonical team id for a source id, or None if unknown."""
    row = get_team(source, source_id)
    if row and row.get("canonical_team_id") is not None:
        return int(row["canonical_team_id"])
    return None


def get_team_abbr(source: str, source_id) -> Optional[str]:
    row = get_team(source, source_id)
    return row.get("abbreviation") if row else None


def team_display_name(source: str, source_id) -> Optional[str]:
    row = get_team(source, source_id)
    return row.get("display_name") if row else None


def refresh_team_cache() -> None:
    """Drop the cached lookups (call after writing a new teams.parquet)."""
    _team_lookups.cache_clear()


# ── Player identity ────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _player_lookups() -> dict[str, dict]:
    df = load_players()
    lookups: dict[str, dict] = {}
    if df.empty:
        return lookups
    for field in [
        "canonical_player_id",
        "wnba_stats_player_id",
        "espn_player_id",
        "balldontlie_player_id",
        "basketball_reference_slug",
    ]:
        if field not in df.columns:
            continue
        lookups[field] = {
            str(r.get(field)): r
            for r in df.to_dict("records")
            if pd.notna(r.get(field)) and str(r.get(field))
        }
    return lookups


def get_player(source: str, source_id) -> Optional[dict]:
    field_map = {
        "wnba_stats": "wnba_stats_player_id",
        "espn": "espn_player_id",
        "balldontlie": "balldontlie_player_id",
        "basketball_reference": "basketball_reference_slug",
    }
    field = field_map.get(source)
    if not field or source_id is None:
        return None
    lookups = _player_lookups()
    return lookups.get(field, {}).get(str(source_id))


def get_player_by_canonical(canonical_id) -> Optional[dict]:
    lookups = _player_lookups()
    return lookups.get("canonical_player_id", {}).get(str(canonical_id))


def get_player_id(source: str, source_id) -> Optional[int]:
    row = get_player(source, source_id)
    if row and row.get("canonical_player_id") is not None:
        return int(row["canonical_player_id"])
    return None


def refresh_player_cache() -> None:
    _player_lookups.cache_clear()


# ── Name normalization helpers ─────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation and suffix noise for matching."""
    import re

    s = str(name or "").strip().lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    # Strip common suffixes like 'Jr', 'Sr', 'III'
    s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", s)
    return s


def match_player_by_name(name: str) -> Optional[dict]:
    """Fuzzy match a player by normalized name. Returns best row or None."""
    target = normalize_name(name)
    if not target:
        return None
    df = load_players()
    if df.empty or "display_name" not in df.columns:
        return None
    df = df.copy()
    df["_n"] = df["display_name"].apply(normalize_name)
    exact = df[df["_n"] == target]
    if not exact.empty:
        return exact.iloc[0].drop(labels=["_n"]).to_dict()
    # Substring fallback (e.g. 'A' Wilson vs 'A'ja Wilson' full name handling)
    sub = df[df["_n"].str.contains(target, na=False) | df["_n"].apply(lambda x: target in x)]
    if not sub.empty:
        return sub.iloc[0].drop(labels=["_n"]).to_dict()
    return None


def refresh_all_caches() -> None:
    refresh_team_cache()
    refresh_player_cache()
