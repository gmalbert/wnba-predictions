"""Data fetching façade.

The application and scripts never call source-specific endpoints directly.
They use the high-level functions here, which:

- route to the right adapter per data type (see utils/source_registry.py);
- cache to league-scoped parquet under data_files/wnba/;
- record source health for the Data Health page;
- never silently return empty frames for source failures (structured fallback).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from utils.adapters.base import SourceUnavailableError
from utils.adapters import espn as espn_adapter
from utils.adapters import wehoop as wehoop_adapter
from utils.adapters import wnba_stats as wnba_stats_adapter
from utils.adapters import odds_api as odds_api_adapter
from utils.adapters import balldontlie as balldontlie_adapter
from utils.data_contracts import GAMES_COLUMNS, TEAM_GAME_COLUMNS, PLAYER_GAME_COLUMNS, INJURIES_COLUMNS, ODDS_COLUMNS
from utils.league_config import get_league_config
from utils.source_registry import priority_for

_ET = dt.timezone(dt.timedelta(hours=-5))  # America/New_York (EST, no DST adjustment for paths)


def _today_et() -> dt.date:
    return dt.datetime.now(_ET).date()


def data_dir() -> Path:
    return get_league_config().storage_namespace()


def normalized_dir() -> Path:
    return data_dir() / "normalized"


def predictions_dir() -> Path:
    return data_dir() / "predictions"


def health_path() -> Path:
    return data_dir() / "source_health.json"


def _read_cache(path: Path) -> pd.DataFrame | None:
    if path.exists():
        try:
            return pd.read_parquet(path)
        except Exception:
            return None
    return None


def _write_cache(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _record_health(source: str, data_type: str, ok: bool, error: str | None = None, records: int = 0) -> None:
    """Persist a source health record to the data health JSON."""
    records_all: list[dict] = []
    p = health_path()
    if p.exists():
        try:
            records_all = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            records_all = []
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    entry = {
        "source": source,
        "data_type": data_type,
        "ok": ok,
        "last_attempt": stamp,
        "last_success": stamp if ok else None,
        "error": error,
        "records": records,
    }
    records_all = [r for r in records_all if not (r.get("source") == source and r.get("data_type") == data_type)]
    records_all.append(entry)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(records_all, indent=2), encoding="utf-8")


def load_health() -> list[dict]:
    p = health_path()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _adapter_for(source: str):
    if source == "wehoop":
        return wehoop_adapter.WehoopAdapter()
    if source == "espn":
        return espn_adapter.EspnAdapter()
    if source == "wnba_stats":
        return wnba_stats_adapter.WnbaStatsAdapter()
    if source == "the_odds_api":
        return odds_api_adapter.OddsApiAdapter()
    if source == "balldontlie":
        return balldontlie_adapter.BalldontlieAdapter()
    raise ValueError(f"Unknown source: {source}")


# ── Schedule ───────────────────────────────────────────────────────────────────

def get_schedule(season: int, force_refresh: bool = False) -> pd.DataFrame:
    """Canonical schedule for a season, cached under normalized/."""
    path = normalized_dir() / "games" / f"season={season}" / "games.parquet"
    if not force_refresh:
        cached = _read_cache(path)
        if cached is not None and not cached.empty:
            return cached

    last_error: Exception | None = None
    for source in priority_for("schedule"):
        try:
            adapter = _adapter_for(source)
            if source == "wehoop":
                df = adapter.fetch_schedule(season)
                # Assign season/type from league config (wehoop schedule has them)
                df["season"] = int(season)
                df["season_type"] = df["season_type"].fillna(get_league_config().default_season_type)
            elif source == "espn":
                start = f"{season}-05-01"
                end = f"{season}-10-15"
                df = adapter.fetch_schedule(start, end)
                df["season"] = int(season)
            else:
                continue
            if not df.empty:
                df = df.reindex(columns=GAMES_COLUMNS)
                _write_cache(df, path)
                _record_health(source, "schedule", True, records=len(df))
                return df
        except SourceUnavailableError as e:
            _record_health(source, "schedule", False, error=str(e))
            last_error = e
            continue
    raise SourceUnavailableError(f"No schedule source available for {season}: {last_error}")


# ── Team / player game stats ──────────────────────────────────────────────────

def get_team_game_stats(season: int, force_refresh: bool = False) -> pd.DataFrame:
    path = normalized_dir() / "team_game_stats" / f"season={season}" / "team_game_stats.parquet"
    if not force_refresh:
        cached = _read_cache(path)
        if cached is not None and not cached.empty:
            return cached

    last_error: Exception | None = None
    for source in priority_for("team_game_stats"):
        try:
            adapter = _adapter_for(source)
            df = adapter.fetch_team_game_stats(season)
            if df.empty:
                continue
            df["league_key"] = get_league_config().league_key
            df["season"] = int(season)
            df = df.reindex(columns=TEAM_GAME_COLUMNS)
            _write_cache(df, path)
            _record_health(source, "team_game_stats", True, records=len(df))
            return df
        except SourceUnavailableError as e:
            _record_health(source, "team_game_stats", False, error=str(e))
            last_error = e
            continue
    raise SourceUnavailableError(f"No team game stats source available for {season}: {last_error}")


def get_player_game_stats(season: int, force_refresh: bool = False) -> pd.DataFrame:
    path = normalized_dir() / "player_game_stats" / f"season={season}" / "player_game_stats.parquet"
    if not force_refresh:
        cached = _read_cache(path)
        if cached is not None and not cached.empty:
            return cached

    last_error: Exception | None = None
    for source in priority_for("player_game_stats"):
        try:
            adapter = _adapter_for(source)
            df = adapter.fetch_player_game_stats(season)
            if df.empty:
                continue
            df["league_key"] = get_league_config().league_key
            df["season"] = int(season)
            df = df.reindex(columns=PLAYER_GAME_COLUMNS)
            _write_cache(df, path)
            _record_health(source, "player_game_stats", True, records=len(df))
            return df
        except SourceUnavailableError as e:
            _record_health(source, "player_game_stats", False, error=str(e))
            last_error = e
            continue
    raise SourceUnavailableError(f"No player game stats source available for {season}: {last_error}")


# ── Injuries ───────────────────────────────────────────────────────────────────

def get_injuries(as_of: str | None = None, force_refresh: bool = False) -> pd.DataFrame:
    path = normalized_dir() / "injuries" / "injuries_latest.parquet"
    if not force_refresh:
        cached = _read_cache(path)
        if cached is not None:
            return cached

    for source in priority_for("injuries"):
        try:
            adapter = _adapter_for(source)
            df = adapter.fetch_injuries(as_of)
            if df.empty:
                continue
            df["league_key"] = get_league_config().league_key
            df = df.reindex(columns=INJURIES_COLUMNS)
            _write_cache(df, path)
            _record_health(source, "injuries", True, records=len(df))
            return df
        except SourceUnavailableError as e:
            _record_health(source, "injuries", False, error=str(e))
            continue
    return pd.DataFrame(columns=INJURIES_COLUMNS)


# ── Odds ───────────────────────────────────────────────────────────────────────

def get_odds(force_refresh: bool = False) -> pd.DataFrame:
    """Current odds snapshot, cached briefly. Returns empty on failure (safe)."""
    path = normalized_dir() / "odds" / "odds_latest.parquet"
    if not force_refresh:
        cached = _read_cache(path)
        if cached is not None and not cached.empty:
            return cached

    for source in priority_for("odds"):
        try:
            adapter = _adapter_for(source)
            df = adapter.fetch_odds()
            if df.empty:
                continue
            df["league_key"] = get_league_config().league_key
            df = df.reindex(columns=ODDS_COLUMNS)
            _write_cache(df, path)
            _record_health(source, "odds", True, records=len(df))
            return df
        except SourceUnavailableError as e:
            _record_health(source, "odds", False, error=str(e))
            continue
    return pd.DataFrame(columns=ODDS_COLUMNS)


# ── Standings ──────────────────────────────────────────────────────────────────

def get_standings(season: int, force_refresh: bool = False) -> pd.DataFrame:
    path = normalized_dir() / "standings" / f"season={season}" / "standings.parquet"
    if not force_refresh:
        cached = _read_cache(path)
        if cached is not None and not cached.empty:
            return cached

    for source in priority_for("standings"):
        try:
            adapter = _adapter_for(source)
            df = adapter.fetch_standings(season)
            if df.empty:
                continue
            _write_cache(df, path)
            _record_health(source, "standings", True, records=len(df))
            return df
        except SourceUnavailableError as e:
            _record_health(source, "standings", False, error=str(e))
            continue
    return pd.DataFrame()


# ── Prediction records ─────────────────────────────────────────────────────────

def load_predictions(date_str: str | None = None) -> pd.DataFrame:
    """Load stored prediction records for a date (YYYY-MM-DD) or the latest."""
    if date_str:
        path = predictions_dir() / f"predictions_{date_str}.parquet"
        return _read_cache(path) or pd.DataFrame()
    # Latest available
    files = sorted(predictions_dir().glob("predictions_*.parquet")) if predictions_dir().exists() else []
    if not files:
        return pd.DataFrame()
    return _read_cache(files[-1]) or pd.DataFrame()


def save_predictions(df: pd.DataFrame, date_str: str) -> Path:
    path = predictions_dir() / f"predictions_{date_str}.parquet"
    _write_cache(df, path)
    return path
