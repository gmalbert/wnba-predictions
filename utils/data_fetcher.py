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
from utils.adapters import odds_api_io as odds_api_io_adapter
from utils.adapters import therundown as therundown_adapter
from utils.adapters import balldontlie as balldontlie_adapter
from utils.data_contracts import (
    AVAILABILITY_COLUMNS,
    GAMES_COLUMNS,
    INJURIES_COLUMNS,
    LINEUP_COLUMNS,
    ODDS_COLUMNS,
    OFFICIALS_COLUMNS,
    OVERSEAS_WORKLOAD_COLUMNS,
    PLAYER_GAME_COLUMNS,
    PLAY_BY_PLAY_COLUMNS,
    TEAM_GAME_COLUMNS,
    TRACKING_COLUMNS,
)
from utils.league_config import get_league_config
from utils.scenario_engine import status_probability
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


def _append_cache(df: pd.DataFrame, path: Path, keys: list[str]) -> None:
    """Append observations while keeping a deterministic de-duplicated ledger."""
    if df is None or df.empty:
        return
    existing = _read_cache(path)
    combined = pd.concat([existing, df], ignore_index=True) if existing is not None else df.copy()
    present_keys = [key for key in keys if key in combined.columns]
    if present_keys:
        combined = combined.drop_duplicates(present_keys, keep="last")
    _write_cache(combined, path)


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
    previous = next(
        (r for r in records_all if r.get("source") == source and r.get("data_type") == data_type),
        {},
    )
    entry = {
        "source": source,
        "data_type": data_type,
        "ok": ok,
        "last_attempt": stamp,
        "last_success": stamp if ok else previous.get("last_success"),
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
    if source == "odds_api_io":
        return odds_api_io_adapter.OddsApiIoAdapter()
    if source == "therundown":
        return therundown_adapter.TheRundownAdapter()
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
            elif source in {"espn", "wnba_stats"}:
                start = f"{season}-04-01"
                end = f"{season}-11-01"
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
            if "observed_at" not in df or df["observed_at"].isna().all():
                df["observed_at"] = df.get("retrieved_at", pd.Series([as_of] * len(df)))
            df = df.reindex(columns=INJURIES_COLUMNS)
            _write_cache(df, path)
            _archive_availability(df, observation_horizon="latest")
            _record_health(source, "injuries", True, records=len(df))
            return df
        except SourceUnavailableError as e:
            _record_health(source, "injuries", False, error=str(e))
            continue
    return pd.DataFrame(columns=INJURIES_COLUMNS)


def _archive_availability(injuries: pd.DataFrame, observation_horizon: str) -> None:
    if injuries is None or injuries.empty:
        return
    obs = pd.DataFrame({
        "league_key": injuries.get("league_key", "wnba"),
        "canonical_game_id": None,
        "canonical_player_id": injuries.get("canonical_player_id"),
        "canonical_team_id": injuries.get("canonical_team_id"),
        "player_name": injuries.get("player_name", ""),
        "status": injuries.get("status", "Unknown"),
        "status_detail": injuries.get("status_detail", injuries.get("description", "")),
        "availability_probability": injuries.get("status", pd.Series("Unknown", index=injuries.index)).map(status_probability),
        "minutes_mean": None,
        "minutes_sd": None,
        "role": None,
        "confirmed_starter": injuries.get("confirmed_starter", False),
        "observation_horizon": observation_horizon,
        "observed_at": injuries.get("observed_at", injuries.get("retrieved_at")),
        "source": injuries.get("source", "unknown"),
        "retrieved_at": injuries.get("retrieved_at"),
    }).reindex(columns=AVAILABILITY_COLUMNS)
    _append_cache(
        obs,
        normalized_dir() / "availability" / "observations.parquet",
        ["canonical_player_id", "canonical_game_id", "observed_at", "source"],
    )


def load_availability_observations(as_of: str | None = None) -> pd.DataFrame:
    """Load the append-only availability/news observation history."""
    df = _read_cache(normalized_dir() / "availability" / "observations.parquet")
    if df is None:
        injuries = _read_cache(normalized_dir() / "injuries" / "injuries_latest.parquet")
        if injuries is None:
            return pd.DataFrame(columns=AVAILABILITY_COLUMNS)
        _archive_availability(injuries, "latest")
        df = _read_cache(normalized_dir() / "availability" / "observations.parquet")
    if df is None:
        return pd.DataFrame(columns=AVAILABILITY_COLUMNS)
    if as_of and "observed_at" in df.columns:
        cutoff = pd.to_datetime(as_of, errors="coerce", utc=True)
        observed = pd.to_datetime(df["observed_at"], errors="coerce", utc=True)
        if pd.notna(cutoff):
            df = df[observed.isna() | (observed <= cutoff)]
    return df.reindex(columns=AVAILABILITY_COLUMNS)


# ── Odds ───────────────────────────────────────────────────────────────────────

def get_odds(force_refresh: bool = False, snapshot_horizon: str = "latest") -> pd.DataFrame:
    """Current combined odds snapshot, cached briefly.

    The default feed combines Odds-API.io and TheRundown. This lets a game
    covered by only one provider still receive market data without making the
    legacy The Odds API quota part of the normal path.
    """
    path = normalized_dir() / "odds" / "odds_latest.parquet"
    if not force_refresh:
        cached = _read_cache(path)
        if cached is not None and not cached.empty:
            # Treat cached odds as fresh for 10 minutes; otherwise refetch
            if "retrieved_at" in cached.columns:
                newest = pd.to_datetime(cached["retrieved_at"], errors="coerce", utc=True).max()
                if pd.notna(newest) and (dt.datetime.now(dt.timezone.utc) - newest).total_seconds() < 600:
                    return cached
            else:
                return cached

    frames: list[pd.DataFrame] = []
    for source in priority_for("odds"):
        try:
            adapter = _adapter_for(source)
            fetch = getattr(adapter, "fetch_odds", None)
            if fetch is None:
                continue
            df = fetch()
            if df.empty:
                _record_health(source, "odds", False, error="No odds returned", records=0)
                continue
            df["league_key"] = get_league_config().league_key
            df["snapshot_horizon"] = snapshot_horizon
            df["is_closing"] = snapshot_horizon == "close"
            df = df.reindex(columns=ODDS_COLUMNS)
            frames.append(df)
            _record_health(source, "odds", True, records=len(df))
        except SourceUnavailableError as e:
            _record_health(source, "odds", False, error=str(e))
            continue

    if frames:
        combined = pd.concat(frames, ignore_index=True).reindex(columns=ODDS_COLUMNS)
        # Remove duplicate rows within a provider while retaining the other
        # provider's observation of the same game/market.
        dedupe_keys = ["canonical_game_id", "book", "market", "name", "point", "source"]
        combined = combined.drop_duplicates(dedupe_keys, keep="last")
        _write_cache(combined, path)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        history_path = normalized_dir() / "odds" / "snapshots" / f"odds_{stamp}_{snapshot_horizon}.parquet"
        _write_cache(combined, history_path)
        _append_cache(
            combined,
            normalized_dir() / "odds" / "odds_history.parquet",
            ["canonical_game_id", "book", "market", "name", "point", "source", "retrieved_at"],
        )
        return combined
    return pd.DataFrame(columns=ODDS_COLUMNS)


def load_odds_history(as_of: str | None = None) -> pd.DataFrame:
    df = _read_cache(normalized_dir() / "odds" / "odds_history.parquet")
    if df is None:
        latest = _read_cache(normalized_dir() / "odds" / "odds_latest.parquet")
        df = latest if latest is not None else pd.DataFrame(columns=ODDS_COLUMNS)
    if as_of and not df.empty and "retrieved_at" in df.columns:
        cutoff = pd.to_datetime(as_of, errors="coerce", utc=True)
        observed = pd.to_datetime(df["retrieved_at"], errors="coerce", utc=True)
        if pd.notna(cutoff):
            df = df[observed.isna() | (observed <= cutoff)]
    return df.reindex(columns=ODDS_COLUMNS)


def get_prop_odds(
    event_ids: list[str] | None = None,
    *,
    force_refresh: bool = False,
    snapshot_horizon: str = "latest",
) -> pd.DataFrame:
    """Fetch/cache timestamped player props across books for current events."""
    path = normalized_dir() / "odds" / "prop_odds_latest.parquet"
    if not force_refresh:
        cached = _read_cache(path)
        if cached is not None and not cached.empty:
            return cached.reindex(columns=ODDS_COLUMNS)
    if not event_ids:
        game_odds = get_odds(force_refresh=force_refresh, snapshot_horizon=snapshot_horizon)
        event_ids = game_odds.get("canonical_game_id", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()
    if not event_ids:
        return pd.DataFrame(columns=ODDS_COLUMNS)
    try:
        adapter = odds_api_adapter.OddsApiAdapter()
        frame = adapter.fetch_prop_odds(event_ids)
    except SourceUnavailableError as exc:
        _record_health("the_odds_api", "player_prop_odds", False, error=str(exc))
        return pd.DataFrame(columns=ODDS_COLUMNS)
    if frame.empty:
        return pd.DataFrame(columns=ODDS_COLUMNS)
    frame["snapshot_horizon"] = snapshot_horizon
    frame["is_closing"] = snapshot_horizon == "close"
    frame = frame.reindex(columns=ODDS_COLUMNS)
    _write_cache(frame, path)
    _append_cache(
        frame,
        normalized_dir() / "odds" / "prop_odds_history.parquet",
        ["canonical_game_id", "book", "market", "name", "point", "retrieved_at"],
    )
    _record_health("the_odds_api", "player_prop_odds", True, records=len(frame))
    return frame


def load_prop_odds_history(as_of: str | None = None) -> pd.DataFrame:
    frame = _read_cache(normalized_dir() / "odds" / "prop_odds_history.parquet")
    if frame is None:
        return pd.DataFrame(columns=ODDS_COLUMNS)
    if as_of and "retrieved_at" in frame.columns:
        cutoff = pd.to_datetime(as_of, errors="coerce", utc=True)
        observed = pd.to_datetime(frame["retrieved_at"], errors="coerce", utc=True)
        if pd.notna(cutoff):
            frame = frame[observed.isna() | (observed <= cutoff)]
    return frame.reindex(columns=ODDS_COLUMNS)


def get_lineup_observations(season: int | None = None, as_of: str | None = None) -> pd.DataFrame:
    """Read optional normalized on/off and lineup observations."""
    path = normalized_dir() / "lineups" / "lineups.parquet"
    df = _read_cache(path)
    if df is None:
        return pd.DataFrame(columns=LINEUP_COLUMNS)
    if season is not None and "season" in df.columns:
        df = df[pd.to_numeric(df["season"], errors="coerce") == int(season)]
    if as_of and "observed_at" in df.columns:
        observed = pd.to_datetime(df["observed_at"], errors="coerce", utc=True)
        cutoff = pd.to_datetime(as_of, errors="coerce", utc=True)
        if pd.notna(cutoff):
            df = df[observed.isna() | (observed <= cutoff)]
    return df.reindex(columns=LINEUP_COLUMNS)


def get_overseas_workload(as_of: str | None = None) -> pd.DataFrame:
    """Read carefully sourced overseas workload rows; unverified rows remain explicit."""
    df = _read_cache(normalized_dir() / "overseas_workload" / "observations.parquet")
    if df is None:
        return pd.DataFrame(columns=OVERSEAS_WORKLOAD_COLUMNS)
    if as_of and "observed_at" in df.columns:
        observed = pd.to_datetime(df["observed_at"], errors="coerce", utc=True)
        cutoff = pd.to_datetime(as_of, errors="coerce", utc=True)
        if pd.notna(cutoff):
            df = df[observed.isna() | (observed <= cutoff)]
    return df.reindex(columns=OVERSEAS_WORKLOAD_COLUMNS)


def get_officials(date_from: str, date_to: str, force_refresh: bool = False) -> pd.DataFrame:
    """Fetch/cache referee crews with observation timestamps."""
    path = normalized_dir() / "officials" / f"officials_{date_from}_{date_to}.parquet"
    if not force_refresh:
        cached = _read_cache(path)
        if cached is not None:
            return cached.reindex(columns=OFFICIALS_COLUMNS)
    for source in priority_for("officials"):
        try:
            adapter = _adapter_for(source)
            fetch = getattr(adapter, "fetch_officials", None)
            if fetch is None:
                continue
            frame = fetch(date_from, date_to)
            if frame.empty:
                continue
            frame = frame.reindex(columns=OFFICIALS_COLUMNS)
            _write_cache(frame, path)
            _record_health(source, "officials", True, records=len(frame))
            return frame
        except SourceUnavailableError as exc:
            _record_health(source, "officials", False, error=str(exc))
    return pd.DataFrame(columns=OFFICIALS_COLUMNS)


def get_play_by_play(season: int, force_refresh: bool = False) -> pd.DataFrame:
    """Fetch/cache canonical play-by-play through the adapter boundary."""
    path = normalized_dir() / "play_by_play" / f"season={season}" / "play_by_play.parquet"
    if not force_refresh:
        cached = _read_cache(path)
        if cached is not None:
            return cached.reindex(columns=PLAY_BY_PLAY_COLUMNS)
    for source in priority_for("play_by_play"):
        try:
            adapter = _adapter_for(source)
            fetch = getattr(adapter, "fetch_play_by_play", None)
            if fetch is None:
                continue
            frame = fetch(season)
            if frame.empty:
                continue
            frame = frame.reindex(columns=PLAY_BY_PLAY_COLUMNS)
            _write_cache(frame, path)
            _record_health(source, "play_by_play", True, records=len(frame))
            return frame
        except SourceUnavailableError as exc:
            _record_health(source, "play_by_play", False, error=str(exc))
    return pd.DataFrame(columns=PLAY_BY_PLAY_COLUMNS)


def get_tracking_observations(season: int | None = None, as_of: str | None = None) -> pd.DataFrame:
    """Read optional tracking observations without inventing unavailable data."""
    frame = _read_cache(normalized_dir() / "tracking" / "observations.parquet")
    if frame is None:
        return pd.DataFrame(columns=TRACKING_COLUMNS)
    if season is not None:
        frame = frame[pd.to_numeric(frame["season"], errors="coerce") == int(season)]
    if as_of:
        cutoff = pd.to_datetime(as_of, errors="coerce", utc=True)
        observed = pd.to_datetime(frame["observed_at"], errors="coerce", utc=True)
        if pd.notna(cutoff):
            frame = frame[observed.isna() | (observed <= cutoff)]
    return frame.reindex(columns=TRACKING_COLUMNS)


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
        df = _read_cache(path)
        return df if df is not None and not df.empty else pd.DataFrame()
    # Latest available
    files = sorted(predictions_dir().glob("predictions_*.parquet")) if predictions_dir().exists() else []
    if not files:
        return pd.DataFrame()
    df = _read_cache(files[-1])
    return df if df is not None and not df.empty else pd.DataFrame()


def save_predictions(df: pd.DataFrame, date_str: str) -> Path:
    path = predictions_dir() / f"predictions_{date_str}.parquet"
    _write_cache(df, path)
    return path
