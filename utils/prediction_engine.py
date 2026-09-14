"""As-of WNBA prediction pipeline with distributions and abstention states."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import numpy as np
import pandas as pd

from utils.data_contracts import PREDICTION_COLUMNS, metadata as contracts_metadata
from utils.data_fetcher import (
    get_lineup_observations,
    get_odds,
    get_overseas_workload,
    get_player_game_stats,
    get_schedule,
    get_team_game_stats,
    load_availability_observations,
    predictions_dir,
)
from utils.evaluation import freeze_prediction_ledger
from utils.feature_engine import build_game_feature_vector, engineer_team_features
from utils.identity import get_team_by_canonical, load_teams
from utils.league_config import get_league_config
from utils.model_utils import (
    FEATURE_COLS_GAME,
    DistributionCalibrator,
    EloSystem,
    align_model_input,
    ensemble_predict_proba,
    get_model_features,
    load_calibrated_models,
    load_distribution_calibrator,
    load_eval_metrics,
    load_regression_model,
    model_dir,
)
from utils.scenario_engine import (
    build_margin_scenarios,
    build_travel_context,
    condition_rotation_for_game,
    context_labels,
    estimate_minutes_distributions,
    inferred_lineup_matchup,
    records_json,
    roster_continuity,
    summarize_margin_scenarios,
    unresolved_star_availability,
)

_CFG = get_league_config()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def win_prob_to_margin(home_win_prob: float) -> float:
    """Convert home win probability to an approximate home scoring margin."""
    probability = np.clip(home_win_prob, 0.01, 0.99)
    return round(float(11.0 * np.log(probability / (1.0 - probability))), 1)


def win_prob_to_spread(home_win_prob: float) -> float:
    """Return the sportsbook-style home spread (negative when home is favored)."""
    return -win_prob_to_margin(home_win_prob)


def assign_confidence_tier(
    model_prob: float,
    market_prob: float | None = None,
    scenario_uncertainty: float = 0.0,
) -> str:
    conviction = max(model_prob, 1.0 - model_prob)
    edge = abs(model_prob - market_prob) if market_prob is not None else None
    if scenario_uncertainty >= 3.0:
        return "Low"
    if conviction >= 0.65 and (edge is None or edge >= 0.05):
        return "High"
    if conviction >= 0.57 or (edge is not None and edge >= 0.02):
        return "Medium"
    return "Low"


def _american_to_prob(odds: object) -> float:
    try:
        value = float(odds)
    except (TypeError, ValueError):
        return 0.5
    if value >= 0:
        return 100.0 / (value + 100.0)
    return abs(value) / (abs(value) + 100.0)


def _market_lookup(odds_df: pd.DataFrame) -> dict[str, dict]:
    """Build de-vigged consensus market records without averaging both sides."""
    if odds_df is None or odds_df.empty or "canonical_game_id" not in odds_df.columns:
        return {}
    lookup: dict[str, dict] = {}

    def store(key: str, record: dict) -> None:
        """Merge provider observations for the same matchup fallback key."""
        existing = lookup.get(key)
        if existing is None:
            lookup[key] = dict(record)
            return
        merged = dict(existing)
        merged.update({field: value for field, value in record.items() if value is not None})
        lookup[key] = merged

    for game_id, group in odds_df.groupby("canonical_game_id"):
        record: dict[str, Any] = {}
        home_name = str(group["home_team"].iloc[0]) if "home_team" in group else ""
        away_name = str(group["away_team"].iloc[0]) if "away_team" in group else ""

        book_probabilities: list[float] = []
        h2h = group[group["market"] == "h2h"].copy()
        for _, book in h2h.groupby("book"):
            home = book[book["name"].astype(str) == home_name]
            away = book[book["name"].astype(str) == away_name]
            if home.empty or away.empty:
                continue
            home_raw = _american_to_prob(home["price"].iloc[-1])
            away_raw = _american_to_prob(away["price"].iloc[-1])
            if home_raw + away_raw > 0:
                book_probabilities.append(home_raw / (home_raw + away_raw))
        if book_probabilities:
            record["home_prob"] = float(np.mean(book_probabilities))

        spreads = group[(group["market"] == "spreads") & (group["name"].astype(str) == home_name)]
        spread_points = pd.to_numeric(spreads.get("point"), errors="coerce").dropna()
        if not spread_points.empty:
            record["spread"] = float(spread_points.mean())

        totals = group[group["market"] == "totals"]
        total_points = pd.to_numeric(totals.get("point"), errors="coerce").dropna()
        if not total_points.empty:
            record["total"] = float(total_points.mean())

        if record:
            store(str(game_id), record)
            game_date = str(group["game_date"].iloc[0])[:10] if "game_date" in group else ""
            if game_date and home_name and away_name:
                store(f"{game_date}|{home_name}|{away_name}", record)
            if home_name and away_name:
                store(f"{home_name}|{away_name}", record)
    return lookup


def _team_name(team_id: int) -> str:
    row = get_team_by_canonical(team_id)
    return str(row.get("display_name")) if row and row.get("display_name") else str(team_id)


def _distribution(
    model,
    calibrator: DistributionCalibrator | None,
    features: pd.DataFrame,
    fallback_mean: float,
    fallback_sd: float,
) -> dict[str, float]:
    point = fallback_mean
    if model is not None:
        try:
            point = float(model.predict(align_model_input(model, features))[0])
        except Exception:
            point = fallback_mean
    if calibrator is None:
        return {
            "mean": float(point), "sd": float(fallback_sd),
            "low": float(point - 1.645 * fallback_sd),
            "high": float(point + 1.645 * fallback_sd),
        }
    predicted = calibrator.predict([point])
    return {key: float(value[0]) for key, value in predicted.items()}


def _latest_feature_data(season: int) -> tuple[pd.DataFrame, pd.DataFrame, int, int | None]:
    """Find the latest cached/fetchable team and player seasons explicitly."""
    team_stats = pd.DataFrame()
    player_stats = pd.DataFrame()
    feature_season = int(season)
    player_season: int | None = None
    for candidate in range(int(season), _CFG.historical_start - 1, -1):
        try:
            team_stats = get_team_game_stats(candidate)
        except Exception:
            team_stats = pd.DataFrame()
        if not team_stats.empty:
            feature_season = candidate
            player_path = _CFG.storage_namespace(
                "normalized", "player_game_stats", f"season={candidate}", "player_game_stats.parquet"
            )
            if player_path.exists():
                try:
                    player_stats = get_player_game_stats(candidate)
                except Exception:
                    player_stats = pd.DataFrame()
            if not player_stats.empty:
                player_season = candidate
            break
    team_ids = set(team_stats.get("canonical_team_id", pd.Series(dtype=object)).dropna().astype(str))
    overlap = set(player_stats.get("canonical_team_id", pd.Series(dtype=object)).dropna().astype(str)) & team_ids
    if player_stats.empty or not overlap:
        player_stats = pd.DataFrame()
        player_season = None
        for candidate in range(int(season) - 1, _CFG.historical_start - 1, -1):
            try:
                candidate_players = get_player_game_stats(candidate)
            except Exception:
                candidate_players = pd.DataFrame()
            candidate_ids = set(
                candidate_players.get("canonical_team_id", pd.Series(dtype=object)).dropna().astype(str)
            )
            if not candidate_players.empty and candidate_ids & team_ids:
                player_stats = candidate_players
                player_season = candidate
                break
    return team_stats, player_stats, feature_season, player_season


def _source_lineup_rows(
    lineups: pd.DataFrame,
    home_team_id: int,
    away_team_id: int,
) -> list[dict]:
    if lineups is None or lineups.empty:
        return []
    rows = lineups[lineups["canonical_team_id"].astype(str).isin([str(home_team_id), str(away_team_id)])]
    rows = rows.sort_values("minutes", ascending=False).groupby("canonical_team_id").head(3)
    return rows.to_dict("records")


def predict_season_games(
    season: int,
    models: dict | None = None,
    elo: EloSystem | None = None,
    odds_df: pd.DataFrame | None = None,
    *,
    as_of: str | None = None,
    stage: str = "midday",
    game_ids: set[str] | None = None,
) -> pd.DataFrame:
    """Generate as-of shadow projections for upcoming games in one season."""
    as_of = as_of or _now()
    models = load_calibrated_models() if models is None else models
    if elo is None:
        elo_path = model_dir() / "elo_system.pkl"
        elo = EloSystem.load(elo_path) if elo_path.exists() else None
    margin_model = load_regression_model("margin")
    total_model = load_regression_model("totals")
    margin_cal = load_distribution_calibrator("margin")
    total_cal = load_distribution_calibrator("totals")
    metrics = load_eval_metrics()
    gate = metrics.get("release_gate") or {
        "status": "shadow_only", "paper_only": True,
        "checks": {
            "untouched_2025_holdout": False,
            "limited_paper_sample": False,
            "limited_paper_games": False,
            "limited_paper_market_coverage": False,
            "minimum_300_priced_bets": False,
            "positive_clv": False,
            "drift_clear": False,
        },
    }

    schedule = get_schedule(season)
    if schedule.empty:
        return pd.DataFrame(columns=PREDICTION_COLUMNS)
    team_stats, player_stats, feature_season, player_season = _latest_feature_data(season)
    if team_stats.empty:
        return pd.DataFrame(columns=PREDICTION_COLUMNS)

    # Historical replays must only see games completed before the horizon.
    cutoff_ts = pd.to_datetime(as_of, errors="coerce", utc=True)
    if pd.notna(cutoff_ts) and "game_date" in team_stats.columns:
        team_dates = pd.to_datetime(team_stats["game_date"], errors="coerce", utc=True)
        team_stats = team_stats[team_dates.isna() | (team_dates < cutoff_ts.normalize())]
    if pd.notna(cutoff_ts) and not player_stats.empty and "game_date" in player_stats.columns:
        player_dates = pd.to_datetime(player_stats["game_date"], errors="coerce", utc=True)
        player_stats = player_stats[player_dates.isna() | (player_dates < cutoff_ts.normalize())]

    team_features: dict[int, pd.DataFrame] = {}
    for team_id, group in team_stats.groupby("canonical_team_id"):
        team_features[int(team_id)] = engineer_team_features(group.sort_values("game_date").reset_index(drop=True))
    prior_rows = [frame.sort_values("game_date").iloc[-1] for frame in team_features.values() if not frame.empty]
    league_prior = pd.DataFrame(prior_rows).median(numeric_only=True) if prior_rows else pd.Series(dtype=float)

    teams = load_teams()
    travel = build_travel_context(schedule, teams)
    availability = load_availability_observations(as_of)
    rotation = estimate_minutes_distributions(player_stats, availability, as_of=as_of)
    lineups = get_lineup_observations(season, as_of)
    overseas = get_overseas_workload(as_of)
    market_lookup = _market_lookup(odds_df) if odds_df is not None else {}

    cutoff_date = pd.to_datetime(as_of, errors="coerce", utc=True).date()
    upcoming = schedule[
        schedule["game_date"].apply(
            lambda value: pd.notna(value) and pd.to_datetime(value).date() >= cutoff_date
        )
    ]
    if game_ids:
        upcoming = upcoming[upcoming["canonical_game_id"].astype(str).isin({str(value) for value in game_ids})]
    results: list[dict] = []
    generated_at = _now()
    feature_schema = contracts_metadata()["schema_version"]
    model_version = "wnba-ensemble-v2"

    for _, game in upcoming.iterrows():
        home_value, away_value = game.get("home_team_id"), game.get("away_team_id")
        if pd.isna(home_value) or pd.isna(away_value):
            continue
        home_id, away_id = int(home_value), int(away_value)
        home_name, away_name = _team_name(home_id), _team_name(away_id)
        game_id = str(game.get("canonical_game_id", ""))
        game_date = str(game.get("game_date", ""))[:10]
        reasons: list[str] = []

        hf, af = team_features.get(home_id), team_features.get(away_id)
        if hf is None or hf.empty:
            reasons.append(f"{home_name}: hierarchical expansion/cold-start prior")
            home_prior = league_prior.copy()
            home_prior["canonical_team_id"] = home_id
            home_prior["game_date"] = cutoff_ts
            hf = pd.DataFrame([home_prior])
        if af is None or af.empty:
            reasons.append(f"{away_name}: hierarchical expansion/cold-start prior")
            away_prior = league_prior.copy()
            away_prior["canonical_team_id"] = away_id
            away_prior["game_date"] = cutoff_ts
            af = pd.DataFrame([away_prior])
        if hf.empty or af.empty:
            reasons.append("Insufficient league history for a cold-start prior")
            home_probability = 0.5
            feature_frame = pd.DataFrame([{column: 0.0 for column in FEATURE_COLS_GAME}])
            home_feature, away_feature = pd.Series(dtype=object), pd.Series(dtype=object)
        else:
            home_feature = hf.sort_values("game_date").iloc[-1].copy()
            away_feature = af.sort_values("game_date").iloc[-1].copy()
            game_context = travel[travel["canonical_game_id"].astype(str) == game_id]
            for prefix, team_id, feature in (("home", home_id, home_feature), ("away", away_id, away_feature)):
                context = game_context[game_context["canonical_team_id"].astype(str) == str(team_id)]
                if not context.empty:
                    for key, value in context.iloc[-1].items():
                        if key not in {"canonical_game_id", "canonical_team_id"}:
                            feature[key] = value
                feature["roster_continuity"] = roster_continuity(player_stats, team_id, as_of=as_of)
            vector = build_game_feature_vector(home_feature, away_feature)
            feature_frame, _ = get_model_features(pd.DataFrame([vector]), FEATURE_COLS_GAME)
            elo_probability = elo.win_probability(home_id, away_id, True) if elo else 0.5
            try:
                learned_probability = float(ensemble_predict_proba(models, feature_frame)[0]) if models else elo_probability
            except Exception:
                learned_probability = elo_probability
            home_probability = float(np.clip(0.8 * learned_probability + 0.2 * elo_probability, 0.01, 0.99))

        if feature_season < season - 1:
            reasons.append(f"Stale team features ({feature_season})")
        if player_season is None:
            reasons.append("No canonically aligned player-minutes history")
        elif player_season < season - 1:
            reasons.append(f"Stale player/minutes history ({player_season})")
        artifact_training = metrics.get("seasons", [])
        if artifact_training and max(artifact_training) < season - 1:
            reasons.append(f"Stale model artifact (trained through {max(artifact_training)})")

        key = game_id
        market = market_lookup.get(key)
        if market is None:
            market = market_lookup.get(f"{game_date}|{home_name}|{away_name}")
        if market is None:
            market = market_lookup.get(f"{home_name}|{away_name}")
        market = market or {}
        market_probability = market.get("home_prob")
        edge = home_probability - market_probability if market_probability is not None else None

        fallback_margin = win_prob_to_margin(home_probability)
        if not hf is None and not af is None and not hf.empty and not af.empty:
            home_points = float(pd.to_numeric(hf.get("points"), errors="coerce").tail(10).mean())
            away_points = float(pd.to_numeric(af.get("points"), errors="coerce").tail(10).mean())
            fallback_total = home_points + away_points
        else:
            fallback_total = 164.0
        margin_dist = _distribution(margin_model, margin_cal, feature_frame, fallback_margin, 9.5)
        total_dist = _distribution(total_model, total_cal, feature_frame, fallback_total, 12.0)

        game_rotation = rotation[
            rotation["canonical_team_id"].astype(str).isin([str(home_id), str(away_id)])
        ] if not rotation.empty else rotation
        context_rows = travel[travel["canonical_game_id"].astype(str) == game_id]
        home_context_frame = context_rows[context_rows["canonical_team_id"].astype(str) == str(home_id)]
        away_context_frame = context_rows[context_rows["canonical_team_id"].astype(str) == str(away_id)]
        home_context = home_context_frame.iloc[-1].to_dict() if not home_context_frame.empty else {}
        away_context = away_context_frame.iloc[-1].to_dict() if not away_context_frame.empty else {}
        game_rotation = condition_rotation_for_game(
            game_rotation, home_id, away_id, home_context, away_context,
            expected_margin=margin_dist["mean"],
        )
        scenarios = build_margin_scenarios(
            margin_dist["mean"], margin_dist["sd"], game_rotation, home_id, away_id
        )
        scenario_summary = summarize_margin_scenarios(scenarios)
        margin_dist["mean"], margin_dist["sd"] = scenario_summary.margin_mean, scenario_summary.margin_sd
        margin_dist["low"] = margin_dist["mean"] - 1.645 * margin_dist["sd"]
        margin_dist["high"] = margin_dist["mean"] + 1.645 * margin_dist["sd"]

        unresolved = unresolved_star_availability(game_rotation, [home_id, away_id])
        if unresolved:
            reasons.append("Unresolved star availability: " + ", ".join(unresolved))
        spread_edge = None
        if market.get("spread") is not None:
            spread_edge = abs(-margin_dist["mean"] - float(market["spread"]))
            if scenario_summary.scenario_uncertainty > max(spread_edge, 1.0):
                reasons.append("Availability uncertainty exceeds the apparent spread edge")
        if gate.get("status") != "production_ready":
            reasons.append("Production release gate has not passed")
        if metrics.get("drift", {}).get("suspended"):
            reasons.append("Artifact automatically suspended by drift checks")

        labels = context_labels(home_context, away_context)
        verified_overseas = overseas[
            overseas["canonical_team_id"].astype(str).isin([str(home_id), str(away_id)])
            & overseas["verified"].fillna(False).astype(bool)
        ].to_dict("records") if not overseas.empty else []
        context_payload = {
            "home": home_context,
            "away": away_context,
            "labels": labels,
            "verified_overseas_workload": verified_overseas,
        }
        source_lineups = _source_lineup_rows(lineups, home_id, away_id)
        matchup = source_lineups or inferred_lineup_matchup(game_rotation, home_id, away_id)

        status = "ready" if not reasons else "no_bet"
        availability_status = "unresolved" if unresolved else "resolved"
        confidence = assign_confidence_tier(
            home_probability, market_probability, scenario_summary.scenario_uncertainty
        )
        results.append({
            "prediction_id": f"{game_id}_{stage}_{generated_at}",
            "game_id": game_id,
            "season": int(season),
            "game_date": game_date,
            "scheduled_start": game.get("scheduled_start"),
            "home_team": home_name,
            "away_team": away_name,
            "home_team_id": home_id,
            "away_team_id": away_id,
            "home_win_prob": round(home_probability, 4),
            "away_win_prob": round(1.0 - home_probability, 4),
            "predicted_spread": round(-margin_dist["mean"], 2),
            "predicted_total": round(total_dist["mean"], 2),
            "margin_mean": round(margin_dist["mean"], 3),
            "margin_sd": round(margin_dist["sd"], 3),
            "margin_low": round(margin_dist["low"], 3),
            "margin_high": round(margin_dist["high"], 3),
            "total_mean": round(total_dist["mean"], 3),
            "total_sd": round(total_dist["sd"], 3),
            "total_low": round(total_dist["low"], 3),
            "total_high": round(total_dist["high"], 3),
            "market_home_prob": round(market_probability, 4) if market_probability is not None else None,
            "market_spread": market.get("spread"),
            "market_total": market.get("total"),
            "edge": round(edge, 4) if edge is not None else None,
            "confidence": confidence,
            "status": status,
            "no_bet_reason": "; ".join(dict.fromkeys(reasons)),
            "paper_only": True if reasons else bool(gate.get("paper_only", True)),
            "release_gate_status": gate.get("status", "shadow_only"),
            "scenario_uncertainty": scenario_summary.scenario_uncertainty,
            "availability_status": availability_status,
            "roster_continuity_home": home_feature.get("roster_continuity") if not home_feature.empty else None,
            "roster_continuity_away": away_feature.get("roster_continuity") if not away_feature.empty else None,
            "travel_context_json": records_json(context_payload),
            "availability_json": records_json(game_rotation),
            "lineup_matchup_json": records_json(matchup),
            "model_version": model_version,
            "feature_schema_version": feature_schema,
            "generated_at": generated_at,
            "stage": stage,
        })
    return pd.DataFrame(results, columns=PREDICTION_COLUMNS)


def generate_and_store_predictions(
    season: int | None = None,
    *,
    stage: str = "midday",
    as_of: str | None = None,
) -> pd.DataFrame:
    """Generate predictions, store the horizon snapshot, and freeze a paper ledger."""
    season = season or _CFG.current_season
    odds = get_odds(snapshot_horizon=stage)
    frame = predict_season_games(season, odds_df=odds, as_of=as_of, stage=stage)
    if frame.empty:
        return frame
    date_str = pd.to_datetime(as_of, errors="coerce", utc=True).date().isoformat() if as_of else dt.date.today().isoformat()
    out = predictions_dir()
    out.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out / f"predictions_{date_str}_{stage}.parquet", index=False)
    # The latest alias keeps the Streamlit read path backwards-compatible.
    frame.to_parquet(out / f"predictions_{date_str}.parquet", index=False)
    freeze_prediction_ledger(frame, horizon=stage, frozen_at=as_of)
    return frame
