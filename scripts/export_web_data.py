"""Export precomputed WNBA artifacts to JSON for the React frontend.

Reads the existing canonical pipeline outputs under ``data_files/wnba/``
and writes a stable set of JSON files to the path supplied via
``--output`` (default ``frontend/public/data/``).

The exporter is the **contract boundary** between the Python pipeline and
the React frontend. No downstream consumer should reach back into
``data_files/wnba/normalized/`` or any parquet file directly; they read
the JSON this script emits.

Run::

    python scripts/export_web_data.py
    python scripts/export_web_data.py --output path/to/data
    python scripts/export_web_data.py --predictions-file predictions_2026-08-25_pre_tip.parquet

Every artifact carries a ``schema_version``, an ISO-8601 ``generated_at``
timestamp, the ``le_key = "wnba"`` and deterministic ordering so two runs
over the same upstream data produce byte-identical files (modulo the
``generated_at`` timestamp which is captured at script invocation).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_contracts import SCHEMA_VERSION  # noqa: E402
from utils.league_config import get_league_config  # noqa: E402

SCHEMA_VERSION_EXPORT = 1
WNBA_RED = "#C8102E"
WNBA_BLUE = "#1D428A"
CONF_COLORS = {"High": "#16a34a", "Medium": "#d97706", "Low": "#6b7280"}


# ── JSON-safe normalization ──────────────────────────────────────────────────


def _json_safe(value: Any) -> Any:
    """Convert numpy / pandas / datetime values to JSON-serializable forms."""
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)
    if isinstance(value, (np.floating,)):
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, (pd.Timestamp, dt.datetime, dt.date)):
        if isinstance(value, pd.Timestamp) and value.tzinfo is None:
            value = value.tz_localize("UTC")
        if isinstance(value, dt.datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, pd.Series):
        return [_json_safe(v) for v in value.tolist()]
    if isinstance(value, pd.DataFrame):
        return [_json_safe(row) for row in value.to_dict("records")]
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, str):
        return value
    return str(value)


def _json_dump(path: Path, payload: Any) -> int:
    """Write ``payload`` as JSON. Returns the file size in bytes."""
    safe = _json_safe(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(safe, indent=2, sort_keys=True, default=str)
    path.write_text(text, encoding="utf-8")
    return path.stat().st_size


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ── Path helpers ─────────────────────────────────────────────────────────────


def _data_root() -> Path:
    return get_league_config().storage_namespace()


def _eval_metrics_path() -> Path:
    return _data_root() / "model_artifacts" / "eval_metrics.json"


def _source_health_path() -> Path:
    return _data_root() / "source_health.json"


def _data_health_report_path() -> Path:
    return _data_root() / "data_health_report.json"


def _predictions_dir() -> Path:
    return _data_root() / "predictions"


def _normalized_root() -> Path:
    return _data_root() / "normalized"


def _reference_root() -> Path:
    return _data_root() / "reference"


def _paper_ledger_path() -> Path:
    return _predictions_dir() / "paper_bet_ledger.parquet"


# ── Common envelope ──────────────────────────────────────────────────────────


def _envelope(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION_EXPORT,
        "generated_at": _now(),
        "league_key": "wnba",
    }
    if extra:
        payload.update(extra)
    return payload


# ── File pickers ─────────────────────────────────────────────────────────────


def _latest_full_predictions() -> Path | None:
    """Return the most recent predictions parquet with the full PREDICTION_COLUMNS schema."""
    from utils.data_contracts import PREDICTION_COLUMNS

    required = set(PREDICTION_COLUMNS)
    directory = _predictions_dir()
    if not directory.exists():
        return None
    candidates = sorted(directory.glob("predictions_*.parquet"))
    for path in reversed(candidates):
        try:
            df = pd.read_parquet(path)
        except Exception:
            continue
        if required.issubset(df.columns):
            return path
    # Fall back to the most recent parquet regardless of schema
    return candidates[-1] if candidates else None


def _season_paths(subdir: str) -> list[tuple[int, Path]]:
    root = _normalized_root() / subdir
    if not root.exists():
        return []
    found: list[tuple[int, Path]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if not name.startswith("season="):
            continue
        try:
            season = int(name.split("=", 1)[1])
        except ValueError:
            continue
        parquet = child / f"{subdir}.parquet"
        if parquet.exists():
            found.append((season, parquet))
    return found


# ── Per-artifact exporters ──────────────────────────────────────────────────


def export_predictions(output: Path) -> int:
    """Build ``predictions.json`` from the latest full-schema prediction parquet."""
    path = _latest_full_predictions()
    games: list[dict[str, Any]] = []
    if path is not None:
        df = pd.read_parquet(path)
        df = df.sort_values(["game_date", "scheduled_start", "home_team"], kind="mergesort")
        for _, row in df.iterrows():
            games.append(_prediction_record(row.to_dict()))
    else:
        # No predictions available yet — emit an empty list so the React app
        # can render its "no upcoming games" empty state instead of crashing.
        pass
    payload = _envelope({"games": games})
    return _json_dump(output / "predictions.json", payload)


def _prediction_record(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "prediction_id": row.get("prediction_id"),
        "game_id": str(row.get("game_id", "")),
        "season": _safe_int(row.get("season")),
        "game_date": _safe_date(row.get("game_date")),
        "scheduled_start": _safe_date(row.get("scheduled_start")),
        "home_team": row.get("home_team"),
        "away_team": row.get("away_team"),
        "home_team_id": _safe_int(row.get("home_team_id")),
        "away_team_id": _safe_int(row.get("away_team_id")),
        "home_win_prob": _safe_float(row.get("home_win_prob")),
        "away_win_prob": _safe_float(row.get("away_win_prob")),
        "predicted_spread": _safe_float(row.get("predicted_spread")),
        "predicted_total": _safe_float(row.get("predicted_total")),
        "margin_mean": _safe_float(row.get("margin_mean")),
        "margin_sd": _safe_float(row.get("margin_sd")),
        "margin_low": _safe_float(row.get("margin_low")),
        "margin_high": _safe_float(row.get("margin_high")),
        "total_mean": _safe_float(row.get("total_mean")),
        "total_sd": _safe_float(row.get("total_sd")),
        "total_low": _safe_float(row.get("total_low")),
        "total_high": _safe_float(row.get("total_high")),
        "market_home_prob": _safe_float(row.get("market_home_prob")),
        "market_spread": _safe_float(row.get("market_spread")),
        "market_total": _safe_float(row.get("market_total")),
        "edge": _safe_float(row.get("edge")),
        "confidence": row.get("confidence") or "Low",
        "status": row.get("status") or "no_bet",
        "no_bet_reason": row.get("no_bet_reason"),
        "paper_only": _safe_bool(row.get("paper_only"), default=True),
        "release_gate_status": row.get("release_gate_status"),
        "scenario_uncertainty": _safe_float(row.get("scenario_uncertainty")),
        "availability_status": row.get("availability_status"),
        "roster_continuity_home": _safe_float(row.get("roster_continuity_home")),
        "roster_continuity_away": _safe_float(row.get("roster_continuity_away")),
        "travel_context": _parse_json(row.get("travel_context_json"), default={"home": {}, "away": {}, "labels": []}),
        "availability": _parse_json(row.get("availability_json"), default=[]),
        "lineup_matchup": _parse_json(row.get("lineup_matchup_json"), default=[]),
        "model_version": row.get("model_version"),
        "feature_schema_version": row.get("feature_schema_version"),
        "generated_at": _safe_date(row.get("generated_at")),
        "stage": row.get("stage"),
    }
    return out


def export_standings(output: Path) -> int:
    seasons_available: list[int] = []
    rows_by_season: dict[int, list[dict[str, Any]]] = {}
    team_names = _team_lookup()
    for season, path in _season_paths("standings"):
        seasons_available.append(season)
        df = pd.read_parquet(path)
        df = df.sort_values(["Conference", "LeagueRank"], kind="mergesort")
        rows_by_season[season] = [_standings_row(r, team_names) for _, r in df.iterrows()]
    seasons_available.sort()
    seasons_payload = []
    for season in seasons_available:
        payload = _envelope({"season": season, "rows": rows_by_season[season]})
        seasons_payload.append(payload)
    # The React Standings page reads `season`, `seasons_available`, and `rows`
    # from a single file (default = current season). We therefore emit a flat
    # "default season" file (`standings.json`) plus one
    # `standings_<season>.json` file per season for client-side season switching.
    default_season = get_league_config().current_season
    default_rows = rows_by_season.get(default_season, [])
    default_payload = _envelope({
        "season": default_season,
        "seasons_available": seasons_available,
        "rows": default_rows,
    })
    size = _json_dump(output / "standings.json", default_payload)
    for entry in seasons_payload:
        _json_dump(output / f"standings_{entry['season']}.json", entry)
    return size


def _standings_row(row: pd.Series, team_names: dict[str, str]) -> dict[str, Any]:
    team_id = _safe_int(row.get("TeamID"))
    city = row.get("TeamCity") or ""
    nickname = row.get("TeamName") or ""
    team_display = team_names.get(str(team_id), f"{city} {nickname}".strip())
    return {
        "team_id": team_id,
        "team": team_display,
        "nickname": nickname or None,
        "city": city,
        "wins": _safe_int(row.get("WINS")),
        "losses": _safe_int(row.get("LOSSES")),
        "win_pct": _safe_float(row.get("WinPCT")),
        "conference": row.get("Conference"),
        "playoff_rank": _safe_int(row.get("PlayoffRank")),
        "streak": row.get("strCurrentStreak"),
        "home_record": row.get("HOME"),
        "road_record": row.get("ROAD"),
        "l10": row.get("L10"),
        "points_per_game": _safe_float(row.get("PointsPG")),
        "opp_points_per_game": _safe_float(row.get("OppPointsPG")),
        "point_diff": _safe_float(row.get("DiffPointsPG")),
        "games_back": _safe_float(row.get("ConferenceGamesBack")),
    }


def export_team_stats(output: Path) -> int:
    seasons_available: list[int] = []
    by_season: dict[int, dict[str, Any]] = {}
    team_names = _team_lookup()
    for season, path in _season_paths("team_game_stats"):
        seasons_available.append(season)
        df = pd.read_parquet(path)
        if df.empty:
            by_season[season] = {"teams": {}}
            continue
        df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
        df = df.sort_values("game_date")
        teams_payload: dict[str, dict[str, Any]] = {}
        for team_id, group in df.groupby("canonical_team_id"):
            teams_payload[str(team_id)] = _team_payload(season, team_id, group, team_names)
        by_season[season] = {"teams": teams_payload}
    seasons_available.sort()
    default_season = get_league_config().current_season
    default_payload = _envelope({
        "season": default_season,
        "seasons_available": seasons_available,
        **by_season.get(default_season, {"teams": {}}),
    })
    size = _json_dump(output / "team_stats.json", default_payload)
    for season in seasons_available:
        _json_dump(output / f"team_stats_{season}.json", _envelope({
            "season": season,
            "seasons_available": seasons_available,
            **by_season.get(season, {"teams": {}}),
        }))
    return size


def _team_payload(season: int, team_id: Any, group: pd.DataFrame, team_names: dict[str, str]) -> dict[str, Any]:
    group = group.sort_values("game_date").reset_index(drop=True)
    feats = _team_rolling_features(group)
    recent = feats.tail(1).iloc[0] if not feats.empty else pd.Series(dtype=float)
    recent_games = group.tail(15).iloc[::-1]
    trends = []
    for _, row in feats.iterrows():
        trends.append({
            "game_date": _safe_date(row.get("game_date")),
            "points": _safe_float(row.get("points")),
            "points_L10": _safe_float(row.get("points_L10")),
        })
    rankings = _team_rankings(season, team_id, group)
    return {
        "team_id": _safe_int(team_id),
        "name": team_names.get(str(team_id), f"Team {team_id}"),
        "summary": {
            "games": int(len(group)),
            "win_pct_L10": _safe_float(recent.get("win_pct_L10")),
            "points_L10": _safe_float(recent.get("points_L10")),
            "rest_days": _safe_float(recent.get("rest_days")),
            "streak": _safe_float(recent.get("streak")),
        },
        "recent_games": [
            {
                "game_date": _safe_date(row.get("game_date")),
                "opponent_team_id": _safe_int(row.get("opponent_team_id")),
                "is_home": _safe_int(row.get("is_home")),
                "points": _safe_int(row.get("points")),
                "win": _safe_int(row.get("win")),
            }
            for _, row in recent_games.iterrows()
        ],
        "trends": trends,
        "rankings": rankings,
    }


def _team_rolling_features(group: pd.DataFrame) -> pd.DataFrame:
    if group.empty:
        return group.copy()
    df = group.copy()
    df["rest_days"] = df["game_date"].diff().dt.days.fillna(3).clip(lower=1, upper=14)
    df["is_b2b"] = (df["rest_days"] == 1).astype(int)
    streaks: list[int] = []
    current = 0
    for win in df["win"]:
        streaks.append(current)
        current = current + 1 if win == 1 else current - 1
    df["streak"] = streaks
    # Match utils.feature_engine: pre-game (shifted) rolling means.
    # compute_win_pct uses min_periods=1; add_rolling_features uses w//2.
    df["win_pct_L10"] = df["win"].rolling(10, min_periods=1).mean().shift(1)
    df["points_L10"] = df["points"].rolling(10, min_periods=5).mean().shift(1)
    return df


def _team_rankings(season: int, team_id: Any, group: pd.DataFrame) -> dict[str, int]:
    if group.empty:
        return {}
    last10 = group.tail(10)
    if last10.empty:
        return {}
    return {
        "points_L10": round(float(last10["points"].mean()), 1),
        "efg_pct_L10": round(float(_safe_efg(last10)), 3),
        "tov_pct_L10": round(float(_safe_tov(last10)), 3),
        "oreb_rate_L10": round(float(_safe_oreb(last10)), 3),
    }


def _safe_efg(df: pd.DataFrame) -> float:
    if not {"field_goals_made", "field_goals_attempted", "three_points_made"}.issubset(df.columns):
        return 0.0
    fga = df["field_goals_attempted"].replace(0, np.nan)
    return float(((df["field_goals_made"] + 0.5 * df["three_points_made"]) / fga).fillna(0).mean())


def _safe_tov(df: pd.DataFrame) -> float:
    if not {"turnovers", "field_goals_attempted", "free_throws_attempted"}.issubset(df.columns):
        return 0.0
    denom = (df["field_goals_attempted"] + 0.44 * df["free_throws_attempted"] + df["turnovers"]).replace(0, np.nan)
    return float((df["turnovers"] / denom).fillna(0).mean())


def _safe_oreb(df: pd.DataFrame) -> float:
    if not {"offensive_rebounds", "defensive_rebounds"}.issubset(df.columns):
        return 0.0
    tot = (df["offensive_rebounds"] + df["defensive_rebounds"]).replace(0, np.nan)
    return float((df["offensive_rebounds"] / tot).fillna(0).mean())


def export_player_stats(output: Path) -> int:
    seasons_available: list[int] = []
    by_season: dict[int, dict[str, Any]] = {}
    player_names = _player_lookup()
    for season, path in _season_paths("player_game_stats"):
        seasons_available.append(season)
        df = pd.read_parquet(path)
        if df.empty:
            by_season[season] = {"players": {}}
            continue
        df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
        df = df.sort_values("game_date")
        mins = pd.to_numeric(df.get("minutes"), errors="coerce").clip(lower=1)
        norm_minutes = get_league_config().normalization_minutes
        for col in ("points", "rebounds", "assists"):
            if col in df.columns:
                df[f"{col}_per40"] = df[col] / mins * norm_minutes
        players_payload: dict[str, dict[str, Any]] = {}
        for player_id, group in df.groupby("canonical_player_id"):
            players_payload[str(player_id)] = _player_payload(group, player_names)
        by_season[season] = {"players": players_payload}
    seasons_available.sort()
    default_season = get_league_config().current_season
    default_payload = _envelope({
        "season": default_season,
        "seasons_available": seasons_available,
        **by_season.get(default_season, {"players": {}}),
    })
    size = _json_dump(output / "player_stats.json", default_payload)
    for season in seasons_available:
        _json_dump(output / f"player_stats_{season}.json", _envelope({
            "season": season,
            "seasons_available": seasons_available,
            **by_season.get(season, {"players": {}}),
        }))
    return size


def _player_payload(group: pd.DataFrame, player_names: dict[str, str]) -> dict[str, Any]:
    group = group.sort_values("game_date").reset_index(drop=True)
    player_id = _safe_int(group["canonical_player_id"].iloc[0]) if not group.empty else None
    name = player_names.get(str(player_id), f"Player {player_id}")
    recent = group.tail(10)
    per40_cols = [c for c in ("points_per40", "rebounds_per40", "assists_per40") if c in group.columns]
    summary = {
        "games": int(len(group)),
        "ppg": round(float(group["points"].mean()), 1) if "points" in group.columns else None,
        "ppg_per40_L10": round(float(recent["points_per40"].mean()), 1) if "points_per40" in recent else None,
        "rpg_per40_L10": round(float(recent["rebounds_per40"].mean()), 1) if "rebounds_per40" in recent else None,
        "apg_per40_L10": round(float(recent["assists_per40"].mean()), 1) if "assists_per40" in recent else None,
    }
    recent_games = [
        {
            "game_date": _safe_date(row.get("game_date")),
            "points": _safe_int(row.get("points")),
            "rebounds": _safe_int(row.get("rebounds")),
            "assists": _safe_int(row.get("assists")),
            "minutes": _safe_float(row.get("minutes")),
            "points_per40": _safe_float(row.get("points_per40")),
        }
        for _, row in group.tail(15).iloc[::-1].iterrows()
    ]
    payload = {
        "player_id": player_id,
        "name": name,
        "team_id": _safe_int(group["canonical_team_id"].iloc[0]) if "canonical_team_id" in group else None,
        "summary": summary,
        "recent_games": recent_games,
    }
    if len(group) >= 3 and "points" in group.columns:
        payload["trends"] = [
            {"game_date": _safe_date(row.get("game_date")), "points": _safe_int(row.get("points"))}
            for _, row in group.iterrows()
        ]
    return payload


def export_model_performance(output: Path) -> int:
    path = _eval_metrics_path()
    if not path.exists():
        payload = _envelope({
            "artifact_status": "missing",
            "release_gate": {"status": "shadow_only", "passed": False, "paper_only": True, "checks": {}},
            "win_model": {},
            "winner_calibration": {"ece": None, "mce": None, "bins": []},
            "holdout_2025": {},
            "walk_forward": [],
            "baselines": {},
            "line_bucket_calibration": {"spread": [], "total": []},
            "paper_ledger": {"priced_bets": 0, "graded_bets": 0, "mean_clv": None,
                             "roi": None, "profit_units": 0.0, "by_market": []},
            "ledger": [],
            "drift": {"max_psi": 0.0, "warning_features": [], "suspended": False},
            "segment_performance": {},
            "margin": {},
            "totals": {},
            "seasons": [],
            "n_rows": 0,
            "holdout_season": None,
            "holdout_rows": 0,
        })
        return _json_dump(output / "model_performance.json", payload)
    metrics = json.loads(path.read_text(encoding="utf-8"))
    ledger = []
    paper_ledger_path = _paper_ledger_path()
    if paper_ledger_path.exists():
        try:
            ledger_df = pd.read_parquet(paper_ledger_path)
            ledger = [_ledger_row(r) for _, r in ledger_df.iterrows()]
        except Exception:
            ledger = []
    payload = _envelope({
        "artifact_status": metrics.get("artifact_status"),
        "release_gate": metrics.get("release_gate", {}),
        "win_model": metrics.get("win_model", {}),
        "winner_calibration": metrics.get("winner_calibration", {"bins": []}),
        "holdout_2025": metrics.get("holdout_2025", {}),
        "walk_forward": metrics.get("walk_forward", []),
        "baselines": metrics.get("baselines", {}),
        "line_bucket_calibration": metrics.get("line_bucket_calibration", {"spread": [], "total": []}),
        "paper_ledger": metrics.get("paper_ledger", {
            "priced_bets": 0, "graded_bets": 0, "mean_clv": None,
            "roi": None, "profit_units": 0.0, "by_market": [],
        }),
        "ledger": ledger,
        "drift": metrics.get("drift", {"max_psi": 0.0, "warning_features": [], "suspended": False}),
        "segment_performance": metrics.get("segment_performance", {}),
        "margin": metrics.get("margin", {}),
        "totals": metrics.get("totals", {}),
        "seasons": metrics.get("seasons", []),
        "n_rows": metrics.get("n_rows", 0),
        "holdout_season": metrics.get("holdout_season"),
        "holdout_rows": metrics.get("holdout_rows", 0),
    })
    return _json_dump(output / "model_performance.json", payload)


def _ledger_row(row: pd.Series) -> dict[str, Any]:
    return {
        "ledger_id": row.get("ledger_id"),
        "prediction_id": row.get("prediction_id"),
        "game_id": str(row.get("game_id", "")),
        "game_date": _safe_date(row.get("game_date")),
        "frozen_at": _safe_date(row.get("frozen_at")),
        "horizon": row.get("horizon"),
        "market": row.get("market"),
        "selection": row.get("selection"),
        "model_probability": _safe_float(row.get("model_probability")),
        "model_line": _safe_float(row.get("model_line")),
        "book": row.get("book"),
        "price": _safe_float(row.get("price")),
        "market_line": _safe_float(row.get("market_line")),
        "closing_price": _safe_float(row.get("closing_price")),
        "closing_line": _safe_float(row.get("closing_line")),
        "clv": _safe_float(row.get("clv")),
        "stake_units": _safe_float(row.get("stake_units")),
        "profit_units": _safe_float(row.get("profit_units")),
        "result": row.get("result"),
        "status": row.get("status"),
        "paper_only": _safe_bool(row.get("paper_only"), default=True),
        "model_version": row.get("model_version"),
    }


def export_data_health(output: Path) -> int:
    source_records = _read_json_list(_source_health_path())
    report = _read_json_object(_data_health_report_path())
    # Preserve registry order — the Streamlit Data Health page renders
    # load_health() records unsorted, and parity depends on row order.
    sources = source_records if source_records else report.get("sources", [])
    capability_registry: list[dict[str, Any]] = []
    for data_type, src_list in _source_priority().items():
        for priority, source in enumerate(src_list, start=1):
            capability_registry.append({
                "data_type": data_type,
                "priority": priority,
                "source": source,
            })
    cfg = get_league_config()
    release_gate_path = _eval_metrics_path()
    gate_status = "shadow_only"
    if release_gate_path.exists():
        try:
            gate = json.loads(release_gate_path.read_text(encoding="utf-8")).get("release_gate", {})
            gate_status = gate.get("status", "shadow_only") or "shadow_only"
        except Exception:
            pass
    artifact_safety = {
        "league": cfg.display_name,
        "season": cfg.current_season,
        "schema": SCHEMA_VERSION,
        "artifact": gate_status.replace("_", " ").title(),
    }
    as_of_coverage = [
        {"dataset": "Odds", "required_history": "Morning, injury report, pre-tip, close", "policy": "Append-only timestamps"},
        {"dataset": "Availability/news", "required_history": "Every status observation and starter confirmation", "policy": "No later observation in replay"},
        {"dataset": "Player minutes", "required_history": "Game-level minutes plus uncertainty", "policy": "Partially pooled cold starts"},
        {"dataset": "Overseas workload", "required_history": "Minutes, return date, provenance", "policy": "Show only verified rows"},
        {"dataset": "Lineups/on-off", "required_history": "Lineup minutes and possessions", "policy": "Inferred rotation if absent"},
    ]
    payload = _envelope({
        "sources": sources,
        "capability_registry": capability_registry,
        "artifact_safety": artifact_safety,
        "as_of_coverage": as_of_coverage,
    })
    return _json_dump(output / "data_health.json", payload)


def _source_priority() -> dict[str, list[str]]:
    from utils.source_registry import SOURCE_PRIORITY
    return {k: list(v) for k, v in SOURCE_PRIORITY.items()}


def export_release_gate(output: Path) -> int:
    path = _eval_metrics_path()
    if not path.exists():
        payload = _envelope({
            "status": "shadow_only",
            "passed": False,
            "paper_only": True,
            "checks": {},
            "holdout_season": None,
            "holdout_rows": 0,
            "priced_bets": 0,
            "mean_clv": None,
            "drift_suspended": False,
        })
        return _json_dump(output / "release_gate.json", payload)
    metrics = json.loads(path.read_text(encoding="utf-8"))
    gate = metrics.get("release_gate", {})
    payload = _envelope({
        "status": gate.get("status", "shadow_only"),
        "passed": bool(gate.get("passed", False)),
        "paper_only": bool(gate.get("paper_only", True)),
        "checks": gate.get("checks", {}),
        "holdout_season": gate.get("holdout_season"),
        "holdout_rows": gate.get("holdout_rows", 0),
        "priced_bets": gate.get("priced_bets", 0),
        "mean_clv": gate.get("mean_clv"),
        "drift_suspended": bool(gate.get("drift_suspended", False)),
    })
    return _json_dump(output / "release_gate.json", payload)


def export_scenario_policy(output: Path) -> int:
    gate_passed = False
    release_gate_path = _eval_metrics_path()
    if release_gate_path.exists():
        try:
            gate = json.loads(release_gate_path.read_text(encoding="utf-8")).get("release_gate", {})
            gate_passed = bool(gate.get("passed", False))
        except Exception:
            gate_passed = False
    payload = _envelope({
        "release_gate_passed": gate_passed,
        "live_stake_units": 0.0,
        "paper_stake_units": 1.0,
        "kelly_enabled": False,
        "reason": (
            "Production gate passed, but Kelly remains disabled until a separate staking review."
            if gate_passed
            else "Production release gate is closed."
        ),
    })
    return _json_dump(output / "scenario_policy.json", payload)


def export_manifest(output: Path) -> int:
    release_gate_path = _eval_metrics_path()
    gate_status = "shadow_only"
    model_version = "wnba-ensemble-unknown"
    feature_schema_version = SCHEMA_VERSION
    if release_gate_path.exists():
        try:
            metrics = json.loads(release_gate_path.read_text(encoding="utf-8"))
            gate_status = metrics.get("release_gate", {}).get("status", "shadow_only") or "shadow_only"
            if metrics.get("win_model", {}).get("n_test"):
                # best-effort: model version surfaces in predictions, not eval metrics
                pass
        except Exception:
            pass
    # Look at the predictions parquet for model_version
    pred_path = _latest_full_predictions()
    if pred_path is not None:
        try:
            df = pd.read_parquet(pred_path)
            if "model_version" in df.columns and df["model_version"].notna().any():
                model_version = str(df["model_version"].dropna().iloc[0])
            if "feature_schema_version" in df.columns and df["feature_schema_version"].notna().any():
                feature_schema_version = str(df["feature_schema_version"].dropna().iloc[0])
        except Exception:
            pass
    payload = _envelope({
        "sport": "WNBA",
        "season": get_league_config().current_season,
        "model_version": model_version,
        "feature_schema_version": feature_schema_version,
        "release_mode": "paper_only" if gate_status != "production_ready" else "production",
        "status": "ok",
        "artifacts": {
            "predictions": "predictions.json",
            "standings": "standings.json",
            "team_stats": "team_stats.json",
            "player_stats": "player_stats.json",
            "model_performance": "model_performance.json",
            "data_health": "data_health.json",
            "release_gate": "release_gate.json",
            "scenario_policy": "scenario_policy.json",
        },
        "thresholds": {
            "predictions_stale_hours": 24,
            "standings_stale_hours": 168,
            "team_stats_stale_hours": 168,
            "model_perf_stale_hours": 720,
        },
    })
    return _json_dump(output / "manifest.json", payload)


# ── Reference helpers ───────────────────────────────────────────────────────


def _team_lookup() -> dict[str, str]:
    path = _reference_root() / "teams.parquet"
    if not path.exists():
        return {}
    df = pd.read_parquet(path)
    return {
        str(row.get("canonical_team_id")): str(row.get("display_name") or "")
        for _, row in df.iterrows()
        if pd.notna(row.get("canonical_team_id"))
    }


def _player_lookup() -> dict[str, str]:
    path = _reference_root() / "players.parquet"
    if not path.exists():
        return {}
    df = pd.read_parquet(path)
    return {
        str(row.get("canonical_player_id")): str(row.get("display_name") or "")
        for _, row in df.iterrows()
        if pd.notna(row.get("canonical_player_id"))
    }


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


# ── Type coercion helpers ───────────────────────────────────────────────────


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return default


def _safe_date(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, str):
        return value
    try:
        ts = pd.to_datetime(value, errors="coerce", utc=True)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    return ts.isoformat().replace("+00:00", "Z")


def _parse_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default
    if isinstance(value, (list, dict)):
        return value
    return default


# ── Entry point ─────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Export WNBA precomputed artifacts to JSON for the React frontend.")
    parser.add_argument("--output", default="frontend/public/data", help="Destination directory")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    sizes: dict[str, int] = {}
    sizes["manifest.json"] = export_manifest(output)
    sizes["predictions.json"] = export_predictions(output)
    sizes["standings.json"] = export_standings(output)
    sizes["team_stats.json"] = export_team_stats(output)
    sizes["player_stats.json"] = export_player_stats(output)
    sizes["model_performance.json"] = export_model_performance(output)
    sizes["data_health.json"] = export_data_health(output)
    sizes["release_gate.json"] = export_release_gate(output)
    sizes["scenario_policy.json"] = export_scenario_policy(output)

    if not args.quiet:
        print(f"Exported {len(sizes)} artifact(s) to {output}")
        for name, size in sizes.items():
            kb = size / 1024.0
            print(f"  {name:<28} {kb:8.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())