"""Prediction pipeline for WNBA game outcomes.

Generates per-game predictions with provenance (model version, feature schema
version, generated_at), market-relative edge, confidence tiers, and abstention
states when inputs are missing or stale.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from utils.data_contracts import PREDICTION_COLUMNS, metadata as contracts_metadata
from utils.data_fetcher import get_schedule, get_team_game_stats, get_odds, predictions_dir
from utils.feature_engine import build_game_feature_vector, engineer_team_features
from utils.league_config import get_league_config
from utils.model_utils import (
    FEATURE_COLS_GAME,
    EloSystem,
    ensemble_predict_proba,
    get_model_features,
    load_models,
    model_dir,
)

_CFG = get_league_config()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def win_prob_to_spread(home_win_prob: float) -> float:
    """Convert home win probability to approximate point spread (WNBA scale)."""
    p = np.clip(home_win_prob, 0.01, 0.99)
    return round(-11.0 * np.log((1.0 - p) / p), 1)


def assign_confidence_tier(model_prob: float, market_prob: float | None = None) -> str:
    edge = abs(model_prob - market_prob) if market_prob is not None else None
    if model_prob >= 0.65 and (edge is None or edge >= 0.05):
        return "High"
    if model_prob >= 0.57 or (edge is not None and edge >= 0.02):
        return "Medium"
    return "Low"


def _market_lookup(odds_df: pd.DataFrame) -> dict[str, dict]:
    """Build {game_id: {home_prob, spread, total}} from canonical odds."""
    if odds_df is None or odds_df.empty or "canonical_game_id" not in odds_df.columns:
        return {}
    lookup: dict[str, dict] = {}
    for gid, grp in odds_df.groupby("canonical_game_id"):
        rec: dict = {}
        # Moneyline (h2h): derive vig-adjusted home prob from names
        ml = grp[grp["market"] == "h2h"].copy()
        if not ml.empty:
            ml["raw_prob"] = ml["price"].apply(_american_to_prob)
            home_name = grp["home_team"].iloc[0] if "home_team" in grp else ""
            if home_name:
                home_rows = ml[ml["name"] == home_name]
                away_rows = ml[ml["name"] != home_name]
                if not home_rows.empty and not away_rows.empty:
                    ph = float(np.mean(home_rows["raw_prob"]))
                    pa = float(np.mean(away_rows["raw_prob"]))
                    vig = ph + pa
                    if vig > 0:
                        rec["home_prob"] = ph / vig
        # Spreads / totals: consensus across books
        sp = grp[grp["market"] == "spreads"]
        if not sp.empty and "point" in sp:
            rec["spread"] = float(np.nanmean(sp["point"].astype(float)))
        tot = grp[grp["market"] == "totals"]
        if not tot.empty and "point" in tot:
            rec["total"] = float(np.nanmean(tot["point"].astype(float)))
        if rec:
            lookup[str(gid)] = rec
    return lookup


def _american_to_prob(odds) -> float:
    try:
        o = float(odds)
    except (TypeError, ValueError):
        return 0.5
    if o >= 0:
        return 100.0 / (o + 100.0)
    return abs(o) / (abs(o) + 100.0)


def predict_season_games(
    season: int,
    models: dict | None = None,
    elo: EloSystem | None = None,
    odds_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Generate predictions for the upcoming (unplayed) games of a season.

    Uses canonical schedule + team game stats to build pre-game feature vectors.
    Returns canonical PREDICTION_COLUMNS rows with provenance.
    """
    if models is None:
        models = load_models()
    if elo is None:
        elo_path = model_dir() / "elo_system.pkl"
        elo = EloSystem.load(elo_path) if elo_path.exists() else None

    schedule = get_schedule(season)
    if schedule.empty:
        return pd.DataFrame(columns=PREDICTION_COLUMNS)

    team_stats = get_team_game_stats(season)
    if team_stats.empty:
        return pd.DataFrame(columns=PREDICTION_COLUMNS)

    # Team feature map (pre-game values per team)
    team_feat: dict[int, pd.DataFrame] = {}
    for tid, grp in team_stats.groupby("canonical_team_id"):
        team_feat[int(tid)] = engineer_team_features(grp.sort_values("game_date").reset_index(drop=True))

    market_lookup = _market_lookup(odds_df) if odds_df is not None else {}

    today = dt.date.today()
    upcoming = schedule[
        schedule["game_date"].apply(
            lambda d: pd.notna(d) and pd.to_datetime(d).date() >= today
        )
    ]

    results = []
    model_ver = "wnba-ensemble-v1"
    feature_schema = contracts_metadata()["schema_version"]
    for _, game in upcoming.iterrows():
        home_id = game.get("home_team_id")
        away_id = game.get("away_team_id")
        if pd.isna(home_id) or pd.isna(away_id):
            continue
        home_id, away_id = int(home_id), int(away_id)

        status = "ready"
        hf = team_feat.get(home_id)
        af = team_feat.get(away_id)
        if hf is None or af is None or hf.empty or af.empty:
            status = "insufficient_history"
            hprob = 0.5
            pred_spread = None
        else:
            home_row = hf.sort_values("game_date").iloc[-1]
            away_row = af.sort_values("game_date").iloc[-1]
            fv = build_game_feature_vector(home_row, away_row)
            X, _ = get_model_features(pd.DataFrame([fv]), FEATURE_COLS_GAME)
            elo_prob = elo.win_probability(home_id, away_id, True) if elo else 0.5
            try:
                ml_prob = float(ensemble_predict_proba(models, X)[0]) if models else 0.5
            except Exception:
                ml_prob = elo_prob
            hprob = (0.75 * ml_prob + 0.25 * elo_prob) if models else elo_prob
            pred_spread = win_prob_to_spread(hprob)

        market = market_lookup.get(str(game.get("canonical_game_id", ""))) or {}
        market_prob = market.get("home_prob")
        edge = round(hprob - market_prob, 3) if market_prob else None

        results.append({
            "prediction_id": f"{game['canonical_game_id']}_{_now()}",
            "game_id": str(game.get("canonical_game_id", "")),
            "season": int(season),
            "game_date": str(game.get("game_date", "")),
            "home_team": str(game.get("home_team_id", "")),
            "away_team": str(game.get("away_team_id", "")),
            "home_team_id": home_id,
            "away_team_id": away_id,
            "home_win_prob": round(hprob, 3),
            "away_win_prob": round(1.0 - hprob, 3),
            "predicted_spread": pred_spread,
            "predicted_total": None,
            "market_home_prob": round(market_prob, 3) if market_prob else None,
            "market_spread": market.get("spread"),
            "market_total": market.get("total"),
            "edge": edge,
            "confidence": assign_confidence_tier(hprob, market_prob),
            "status": status,
            "model_version": model_ver,
            "feature_schema_version": feature_schema,
            "generated_at": _now(),
            "stage": "midday",
        })

    return pd.DataFrame(results, columns=PREDICTION_COLUMNS)


def generate_and_store_predictions(season: int | None = None) -> pd.DataFrame:
    """Generate predictions for the current season and persist to disk."""
    season = season or _CFG.current_season
    odds_df = get_odds()
    df = predict_season_games(season, odds_df=odds_df)
    if not df.empty:
        date_str = dt.date.today().isoformat()
        out = predictions_dir()
        out.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out / f"predictions_{date_str}.parquet", index=False)
    return df
