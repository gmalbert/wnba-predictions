"""Canonical data contracts for the WNBA application.

Every source adapter normalizes raw payloads into these stable schemas so the
feature engine, prediction engine, and UI never touch source-specific columns.

Schema changes here should be coordinated with a schema_version bump and a
re-normalization of raw data.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "2.0.0"

# ── Canonical column lists (order matters for stable parquet output) ──────────

GAMES_COLUMNS = [
    "league_key",
    "season",
    "season_type",
    "canonical_game_id",
    "source_game_id",
    "game_date",
    "scheduled_start",
    "home_team_id",
    "away_team_id",
    "home_score",
    "away_score",
    "status",
    "neutral_site",
    "overtime_periods",
    "season_phase",
    "is_commissioners_cup",
    "is_playoff",
    "venue_name",
    "venue_city",
    "venue_latitude",
    "venue_longitude",
    "venue_timezone",
    "source",
    "retrieved_at",
]

TEAM_GAME_COLUMNS = [
    "league_key",
    "season",
    "season_type",
    "canonical_game_id",
    "canonical_team_id",
    "opponent_team_id",
    "is_home",
    "game_date",
    "win",
    "points",
    "field_goals_made",
    "field_goals_attempted",
    "three_points_made",
    "three_points_attempted",
    "free_throws_made",
    "free_throws_attempted",
    "offensive_rebounds",
    "defensive_rebounds",
    "assists",
    "turnovers",
    "steals",
    "blocks",
    "personal_fouls",
    "minutes",
    "possessions",
    "source",
    "retrieved_at",
]

PLAYER_GAME_COLUMNS = [
    "league_key",
    "season",
    "season_type",
    "canonical_game_id",
    "canonical_player_id",
    "player_name",
    "canonical_team_id",
    "opponent_team_id",
    "game_date",
    "is_home",
    "started",
    "minutes",
    "points",
    "rebounds",
    "assists",
    "steals",
    "blocks",
    "turnovers",
    "field_goals_made",
    "field_goals_attempted",
    "three_points_made",
    "three_points_attempted",
    "free_throws_made",
    "free_throws_attempted",
    "source",
    "retrieved_at",
]

TEAMS_COLUMNS = [
    "canonical_team_id",
    "canonical_franchise_id",
    "display_name",
    "city",
    "nickname",
    "abbreviation",
    "conference",
    "active_from",
    "active_to",
    "venue",
    "latitude",
    "longitude",
    "wnba_stats_team_id",
    "espn_team_id",
    "balldontlie_team_id",
    "basketball_reference_slug",
    "wehoop_team_id",
]

PLAYERS_COLUMNS = [
    "canonical_player_id",
    "display_name",
    "normalized_name",
    "birth_date",
    "active_from",
    "active_to",
    "wnba_stats_player_id",
    "espn_player_id",
    "balldontlie_player_id",
    "basketball_reference_slug",
]

INJURIES_COLUMNS = [
    "league_key",
    "canonical_player_id",
    "canonical_team_id",
    "player_name",
    "team_name",
    "status",
    "description",
    "status_detail",
    "confirmed_starter",
    "observed_at",
    "source",
    "retrieved_at",
]

ODDS_COLUMNS = [
    "league_key",
    "season",
    "canonical_game_id",
    "game_date",
    "home_team",
    "away_team",
    "book",
    "market",
    "name",
    "price",
    "point",
    "commence_time",
    "snapshot_horizon",
    "is_closing",
    "market_last_update",
    "source",
    "retrieved_at",
]

# Append-only observation contracts.  These intentionally keep observation
# time separate from event time so historical replays can reproduce exactly
# what was knowable at morning, injury-report, and pre-tip horizons.
AVAILABILITY_COLUMNS = [
    "league_key",
    "canonical_game_id",
    "canonical_player_id",
    "canonical_team_id",
    "player_name",
    "status",
    "status_detail",
    "availability_probability",
    "minutes_mean",
    "minutes_sd",
    "role",
    "confirmed_starter",
    "observation_horizon",
    "observed_at",
    "source",
    "retrieved_at",
]

LINEUP_COLUMNS = [
    "league_key",
    "season",
    "canonical_game_id",
    "canonical_team_id",
    "lineup_id",
    "player_ids",
    "minutes",
    "possessions",
    "offensive_rating",
    "defensive_rating",
    "net_rating",
    "observed_at",
    "source",
    "retrieved_at",
]

OVERSEAS_WORKLOAD_COLUMNS = [
    "league_key",
    "canonical_player_id",
    "canonical_team_id",
    "competition",
    "club",
    "season_start",
    "season_end",
    "minutes",
    "games",
    "return_date",
    "origin_city",
    "verified",
    "observed_at",
    "source",
    "retrieved_at",
]

OFFICIALS_COLUMNS = [
    "league_key",
    "canonical_game_id",
    "game_date",
    "official_id",
    "official_name",
    "official_position",
    "observed_at",
    "source",
    "retrieved_at",
]

PLAY_BY_PLAY_COLUMNS = [
    "league_key",
    "season",
    "canonical_game_id",
    "event_id",
    "sequence_number",
    "period",
    "clock",
    "event_type",
    "event_text",
    "canonical_team_id",
    "canonical_player_id",
    "home_score",
    "away_score",
    "source",
    "retrieved_at",
]

TRACKING_COLUMNS = [
    "league_key",
    "season",
    "canonical_game_id",
    "canonical_team_id",
    "canonical_player_id",
    "metric",
    "value",
    "unit",
    "observed_at",
    "source",
    "retrieved_at",
]

TRAVEL_CONTEXT_COLUMNS = [
    "league_key",
    "season",
    "canonical_game_id",
    "canonical_team_id",
    "game_date",
    "is_home",
    "rest_days",
    "games_last_4_days",
    "games_last_7_days",
    "travel_miles",
    "timezone_shift_hours",
    "is_cross_country",
    "is_early_start",
    "is_commissioners_cup",
    "is_playoff",
    "neutral_site",
    "observed_at",
]

BET_LEDGER_COLUMNS = [
    "ledger_id",
    "prediction_id",
    "game_id",
    "game_date",
    "frozen_at",
    "horizon",
    "market",
    "selection",
    "model_probability",
    "model_line",
    "book",
    "price",
    "market_line",
    "closing_price",
    "closing_line",
    "clv",
    "stake_units",
    "result",
    "profit_units",
    "status",
    "paper_only",
    "model_version",
]

PREDICTION_COLUMNS = [
    "prediction_id",
    "game_id",
    "season",
    "game_date",
    "scheduled_start",
    "home_team",
    "away_team",
    "home_team_id",
    "away_team_id",
    "home_win_prob",
    "away_win_prob",
    "predicted_spread",
    "predicted_total",
    "margin_mean",
    "margin_sd",
    "margin_low",
    "margin_high",
    "total_mean",
    "total_sd",
    "total_low",
    "total_high",
    "market_home_prob",
    "market_spread",
    "market_total",
    "edge",
    "confidence",
    "status",
    "no_bet_reason",
    "paper_only",
    "release_gate_status",
    "scenario_uncertainty",
    "availability_status",
    "roster_continuity_home",
    "roster_continuity_away",
    "travel_context_json",
    "availability_json",
    "lineup_matchup_json",
    "model_version",
    "feature_schema_version",
    "generated_at",
    "stage",
]


# ── Validation helpers ─────────────────────────────────────────────────────────

def _require_columns(df, columns: list[str], name: str) -> None:
    """Raise if df is missing any canonical column."""
    import pandas as pd

    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing canonical columns: {missing}")


def validate_frame(df, columns: list[str], name: str) -> None:
    """Validate a DataFrame against a canonical schema (columns + types)."""
    import pandas as pd

    if df is None or not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name} must be a pandas DataFrame")
    _require_columns(df, columns, name)


def schema_hash(columns: list[str]) -> str:
    """Stable hash of a column list, used in artifact metadata."""
    import hashlib

    return hashlib.sha256("\n".join(columns).encode()).hexdigest()[:12]


def metadata() -> dict[str, Any]:
    """Standard metadata blob attached to saved artifacts."""
    return {
        "schema_version": SCHEMA_VERSION,
        "columns_hash": {
            "games": schema_hash(GAMES_COLUMNS),
            "team_game": schema_hash(TEAM_GAME_COLUMNS),
            "player_game": schema_hash(PLAYER_GAME_COLUMNS),
            "availability": schema_hash(AVAILABILITY_COLUMNS),
            "lineup": schema_hash(LINEUP_COLUMNS),
            "odds": schema_hash(ODDS_COLUMNS),
            "bet_ledger": schema_hash(BET_LEDGER_COLUMNS),
            "officials": schema_hash(OFFICIALS_COLUMNS),
            "play_by_play": schema_hash(PLAY_BY_PLAY_COLUMNS),
            "tracking": schema_hash(TRACKING_COLUMNS),
        },
    }


def to_json(obj: Any) -> str:
    return json.dumps(obj, default=str, sort_keys=True)
