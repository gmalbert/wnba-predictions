"""wehoop adapter — WNBA data from ESPN via the sportsdataverse wehoop-data repo.

wehoop-py 0.0.8 hardcodes ``master`` in its data URLs, but the data repo's
default branch is ``main``, so the package's own functions 404. This adapter
therefore fetches the published parquet files directly from the ``main`` branch
and normalizes them to the canonical schemas in utils/data_contracts.py.

Coverage (verified against the repo listing): team_box 2003-2022, player_box
2003-2022, schedules through 2023, play_by_play through 2022.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

from utils.adapters.base import SourceUnavailableError
from utils.data_contracts import GAMES_COLUMNS, TEAM_GAME_COLUMNS, PLAYER_GAME_COLUMNS
from utils.league_config import get_league_config

_DATA_BASE = "https://raw.githubusercontent.com/saiemgilani/wehoop-data/main/wnba"
_TEAM_BOX_URL = _DATA_BASE + "/team_box/parquet/team_box_{season}.parquet"
_PLAYER_BOX_URL = _DATA_BASE + "/player_box/parquet/player_box_{season}.parquet"
_SCHEDULE_URL = _DATA_BASE + "/schedules/parquet/wnba_schedule_{season}.parquet"
_PBP_URL = _DATA_BASE + "/pbp/parquet/play_by_play_{season}.parquet"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _read_season(url_template: str, season: int) -> pd.DataFrame:
    """Download one season parquet from the wehoop-data repo (main branch)."""
    url = url_template.format(season=season)
    try:
        df = pd.read_parquet(url)
    except Exception as e:
        raise SourceUnavailableError(f"wehoop fetch failed for season {season}: {e}") from e
    if df is None or df.empty:
        raise SourceUnavailableError(f"wehoop returned no rows for season {season}")
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def _to_float(v):
    try:
        if pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v):
    f = _to_float(v)
    return int(f) if f is not None else None


def _bool_flag(v) -> bool:
    try:
        return bool(v)
    except Exception:
        return False


class WehoopAdapter:
    """Adapter around the wehoop-data parquet files (ESPN-backed)."""

    source_name = "wehoop"

    def __init__(self) -> None:
        self.cfg = get_league_config()

    # ── Schedule / games ──────────────────────────────────────────────────────

    def fetch_schedule(self, season: int) -> pd.DataFrame:
        sched = _read_season(_SCHEDULE_URL, season)
        rows = []
        for _, g in sched.iterrows():
            game_id = str(g.get("game_id", g.get("id", "")))
            home_id = g.get("home_id")
            away_id = g.get("away_id")
            home_score = g.get("home_score")
            away_score = g.get("away_score")
            status = str(g.get("status_type_state", ""))
            season_type = str(g.get("season_type", ""))
            # Map ESPN season_type codes to labels: 1 = pre, 2 = regular, 3 = postseason
            if season_type == "2":
                season_type = self.cfg.default_season_type
            elif season_type == "3":
                season_type = self.cfg.playoff_label
            rows.append({
                "league_key": self.cfg.league_key,
                "season": int(season),
                "season_type": season_type,
                "canonical_game_id": game_id,
                "source_game_id": game_id,
                "game_date": str(g.get("game_date", ""))[:10],
                "scheduled_start": g.get("game_date_time") or g.get("date"),
                "home_team_id": _to_int(home_id),
                "away_team_id": _to_int(away_id),
                "home_score": _to_int(home_score),
                "away_score": _to_int(away_score),
                "status": status,
                "neutral_site": _bool_flag(g.get("neutral_site")),
                "overtime_periods": None,
                "source": self.source_name,
                "retrieved_at": _now(),
            })
        return pd.DataFrame(rows, columns=GAMES_COLUMNS)

    # ── Team box scores ───────────────────────────────────────────────────────

    def fetch_team_game_stats(self, season: int) -> pd.DataFrame:
        box = _read_season(_TEAM_BOX_URL, season)
        rows = []
        for _, r in box.iterrows():
            rows.append({
                "league_key": self.cfg.league_key,
                "season": int(r.get("season", season)),
                "season_type": str(r.get("season_type", self.cfg.default_season_type)),
                "canonical_game_id": str(r.get("game_id", "")),
                "canonical_team_id": _to_int(r.get("team_id")),
                "opponent_team_id": _to_int(r.get("opponent_team_id")),
                "is_home": 1 if str(r.get("team_home_away", "")).lower() == "home" else 0,
                "game_date": str(r.get("game_date", ""))[:10],
                "win": 1 if _bool_flag(r.get("team_winner")) else 0,
                "points": _to_int(r.get("team_score")),
                "field_goals_made": _to_int(r.get("field_goals_made")),
                "field_goals_attempted": _to_int(r.get("field_goals_attempted")),
                "three_points_made": _to_int(r.get("three_point_field_goals_made")),
                "three_points_attempted": _to_int(r.get("three_point_field_goals_attempted")),
                "free_throws_made": _to_int(r.get("free_throws_made")),
                "free_throws_attempted": _to_int(r.get("free_throws_attempted")),
                "offensive_rebounds": _to_int(r.get("offensive_rebounds")),
                "defensive_rebounds": _to_int(r.get("defensive_rebounds")),
                "assists": _to_int(r.get("assists")),
                "turnovers": _to_int(r.get("turnovers")),
                "steals": _to_int(r.get("steals")),
                "blocks": _to_int(r.get("blocks")),
                "personal_fouls": _to_int(r.get("fouls")),
                "minutes": _to_float(r.get("minutes")),
                "possessions": None,
                "source": self.source_name,
                "retrieved_at": _now(),
            })
        return pd.DataFrame(rows, columns=TEAM_GAME_COLUMNS)

    # ── Player box scores ─────────────────────────────────────────────────────

    def fetch_player_game_stats(self, season: int) -> pd.DataFrame:
        box = _read_season(_PLAYER_BOX_URL, season)
        rows = []
        for _, r in box.iterrows():
            rows.append({
                "league_key": self.cfg.league_key,
                "season": int(r.get("season", season)),
                "season_type": str(r.get("season_type", self.cfg.default_season_type)),
                "canonical_game_id": str(r.get("game_id", "")),
                "canonical_player_id": _to_int(r.get("athlete_id")),
                "canonical_team_id": _to_int(r.get("team_id")),
                "started": 1 if _bool_flag(r.get("starter")) else 0,
                "minutes": _to_float(r.get("minutes")),
                "points": _to_int(r.get("points")),
                "rebounds": _to_int(r.get("rebounds")),
                "assists": _to_int(r.get("assists")),
                "steals": _to_int(r.get("steals")),
                "blocks": _to_int(r.get("blocks")),
                "turnovers": _to_int(r.get("turnovers")),
                "field_goals_made": _to_int(r.get("field_goals_made")),
                "field_goals_attempted": _to_int(r.get("field_goals_attempted")),
                "three_points_made": _to_int(r.get("three_point_field_goals_made")),
                "three_points_attempted": _to_int(r.get("three_point_field_goals_attempted")),
                "free_throws_made": _to_int(r.get("free_throws_made")),
                "free_throws_attempted": _to_int(r.get("free_throws_attempted")),
                "source": self.source_name,
                "retrieved_at": _now(),
            })
        return pd.DataFrame(rows, columns=PLAYER_GAME_COLUMNS)

    # ── Play-by-play (raw; normalized elsewhere) ──────────────────────────────

    def fetch_play_by_play(self, season: int) -> pd.DataFrame:
        return _read_season(_PBP_URL, season)

    # ── Rosters ───────────────────────────────────────────────────────────────

    def fetch_rosters(self, season: int) -> pd.DataFrame:
        """Derive rosters from the player box scores for a season."""
        box = self.fetch_player_game_stats(season)
        if box.empty:
            return pd.DataFrame()
        rosters = (
            box[["canonical_player_id", "canonical_team_id", "season"]]
            .drop_duplicates()
            .rename(columns={
                "canonical_player_id": "player_id",
                "canonical_team_id": "team_id",
            })
        )
        return rosters

    # ── Injuries (ESPN via wehoop) ────────────────────────────────────────────

    def fetch_injuries(self, as_of: str | None = None) -> pd.DataFrame:
        # wehoop-py does not expose WNBA injuries; ESPN endpoint used by the espn adapter.
        raise SourceUnavailableError("wehoop adapter has no injury feed")


def wehoop_cache_path(season: int, kind: str) -> Path:
    """League-scoped cache path for wehoop data (team_box, player_box, schedule, pbp)."""
    cfg = get_league_config()
    return cfg.storage_namespace("raw", "wehoop", str(season), f"{kind}.parquet")
