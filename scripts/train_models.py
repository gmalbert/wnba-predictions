"""Train and audit WNBA winner, margin, and total distributions.

The default replay keeps 2025 untouched, uses expanding-season folds and
recency weights, calibrates all three target distributions separately, and
persists an explicit production release gate.  A failed gate is expected to
leave the artifact in shadow/paper-only mode.

Run: python scripts/train_models.py --seasons 2018,2019,...,2025
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_fetcher import (  # noqa: E402
    get_player_game_stats,
    get_schedule,
    get_team_game_stats,
    load_odds_history,
)
from utils.evaluation import evaluate_market_baseline, ledger_summary  # noqa: E402
from utils.feature_engine import build_training_dataset  # noqa: E402
from utils.identity import load_teams  # noqa: E402
from utils.league_config import get_league_config  # noqa: E402
from utils.model_utils import (  # noqa: E402
    FEATURE_COLS_GAME,
    FEATURE_COLS_MARGIN,
    FEATURE_COLS_TOTALS,
    DistributionCalibrator,
    EloSystem,
    align_model_input,
    calibration_report,
    calibrate_models,
    drift_report,
    ensemble_predict_proba,
    evaluate_distribution,
    evaluate_model,
    expanding_season_eval,
    get_model_features,
    model_dir,
    release_gate,
    save_calibrated_models,
    save_distribution_calibrator,
    save_eval_metrics,
    save_models,
    save_regression_model,
    season_recency_weights,
    train_ensemble,
    train_margin_model,
    train_totals_model,
)
from utils.scenario_engine import build_travel_context  # noqa: E402


def _schedule_from_team_games(team_games: pd.DataFrame, season: int) -> pd.DataFrame:
    """Reconstruct completed schedule rows when a dedicated feed is unavailable."""
    rows: list[dict] = []
    season_config_path = ROOT / "config" / "seasons.toml"
    regular_end = None
    if season_config_path.exists():
        with season_config_path.open("rb") as handle:
            configured = tomllib.load(handle).get("season_dates", {}).get(str(season), {})
        regular_end = pd.to_datetime(configured.get("end"), errors="coerce")
    for game_id, group in team_games.groupby("canonical_game_id"):
        if len(group) < 2:
            continue
        home_rows = group[pd.to_numeric(group["is_home"], errors="coerce") == 1]
        home = home_rows.iloc[0] if not home_rows.empty else group.iloc[0]
        away_rows = group[group["canonical_team_id"].astype(str) != str(home["canonical_team_id"])]
        if away_rows.empty:
            continue
        away = away_rows.iloc[0]
        season_type = str(home.get("season_type", "Regular Season"))
        game_date = pd.to_datetime(home.get("game_date"), errors="coerce")
        phase = (
            "playoffs"
            if "playoff" in season_type.lower() or (pd.notna(regular_end) and pd.notna(game_date) and game_date > regular_end)
            else "regular"
        )
        rows.append({
            "league_key": "wnba",
            "season": int(season),
            "season_type": season_type,
            "canonical_game_id": str(game_id),
            "game_date": home.get("game_date"),
            "scheduled_start": home.get("game_date"),
            "home_team_id": home.get("canonical_team_id"),
            "away_team_id": away.get("canonical_team_id"),
            "home_score": home.get("points"),
            "away_score": away.get("points"),
            "neutral_site": False,
            "season_phase": phase,
            "is_commissioners_cup": False,
            "is_playoff": phase == "playoffs",
            "retrieved_at": home.get("retrieved_at"),
        })
    return pd.DataFrame(rows)


def build_dataset(seasons: list[int]) -> pd.DataFrame:
    """Build canonical, leakage-safe features with optional context enrichment."""
    frames: list[pd.DataFrame] = []
    teams = load_teams()
    for season in seasons:
        try:
            tg = get_team_game_stats(season)
        except Exception as exc:
            print(f"[{season}] unavailable: {exc}", flush=True)
            continue
        if tg.empty:
            continue
        try:
            schedule = get_schedule(season)
        except Exception:
            schedule = pd.DataFrame()
        if schedule.empty:
            schedule = _schedule_from_team_games(tg, season)
        context = build_travel_context(schedule, teams)
        try:
            player_games = get_player_game_stats(season)
        except Exception:
            player_games = pd.DataFrame()
        frame = build_training_dataset(tg, context_df=context, player_game_df=player_games)
        if not frame.empty:
            frame["season"] = int(season)
            frames.append(frame)
        print(
            f"[{season}] training rows={len(frame)} player_rows={len(player_games)} context_rows={len(context)}",
            flush=True,
        )
    if not frames:
        raise RuntimeError("No training data available")
    data = pd.concat(frames, ignore_index=True).sort_values("game_date").reset_index(drop=True)
    return _attach_historical_market(data)


def _attach_historical_market(data: pd.DataFrame) -> pd.DataFrame:
    """Attach latest/closing consensus lines when timestamped history exists."""
    history = load_odds_history()
    if history.empty or "canonical_game_id" not in history.columns:
        return data
    odds = history.copy()
    odds["canonical_game_id"] = odds["canonical_game_id"].astype(str)
    odds["_observed"] = pd.to_datetime(odds.get("retrieved_at"), errors="coerce", utc=True)
    if "is_closing" in odds.columns:
        closing_flags = odds["is_closing"].eq(True)
        if closing_flags.any():
            closing_ids = set(odds.loc[closing_flags, "canonical_game_id"])
            odds = odds[closing_flags | ~odds["canonical_game_id"].isin(closing_ids)]
    records: list[dict] = []
    for game_id, group in odds.groupby("canonical_game_id"):
        group = group.sort_values("_observed")
        home_name = str(group.get("home_team", pd.Series([""])).iloc[-1])
        away_name = str(group.get("away_team", pd.Series([""])).iloc[-1])
        record: dict = {"game_id": str(game_id)}
        probabilities: list[float] = []
        for _, book in group[group["market"] == "h2h"].groupby("book"):
            latest = book.drop_duplicates("name", keep="last")
            home = latest[latest["name"].astype(str) == home_name]
            away = latest[latest["name"].astype(str) == away_name]
            if home.empty or away.empty:
                continue
            hp = _american_probability(home["price"].iloc[-1])
            ap = _american_probability(away["price"].iloc[-1])
            if hp is not None and ap is not None and hp + ap > 0:
                probabilities.append(hp / (hp + ap))
        if probabilities:
            record["market_home_prob"] = float(np.mean(probabilities))
        spread = group[(group["market"] == "spreads") & (group["name"].astype(str) == home_name)]
        points = pd.to_numeric(spread.get("point"), errors="coerce").dropna()
        if not points.empty:
            record["market_spread"] = float(points.mean())
        totals = pd.to_numeric(group.loc[group["market"] == "totals", "point"], errors="coerce").dropna()
        if not totals.empty:
            record["market_total"] = float(totals.mean())
        records.append(record)
    market = pd.DataFrame(records)
    if market.empty:
        return data
    result = data.copy()
    result["game_id"] = result["game_id"].astype(str)
    return result.merge(market, on="game_id", how="left")


def _american_probability(price: object) -> float | None:
    try:
        value = float(price)
    except (TypeError, ValueError):
        return None
    return 100.0 / (value + 100.0) if value > 0 else abs(value) / (abs(value) + 100.0) if value < 0 else None


def _split_fit_calibration(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reserve the latest season/tail for calibration without random splitting."""
    seasons = sorted(pd.to_numeric(data["season"], errors="coerce").dropna().astype(int).unique())
    if len(seasons) >= 2:
        calibration_season = seasons[-1]
        fit = data[data["season"] < calibration_season]
        calibration = data[data["season"] == calibration_season]
        if len(fit) >= 100 and len(calibration) >= 25:
            return fit.reset_index(drop=True), calibration.reset_index(drop=True)
    split = max(int(len(data) * 0.8), 1)
    return data.iloc[:split].reset_index(drop=True), data.iloc[split:].reset_index(drop=True)


def _fit_candidate(train: pd.DataFrame) -> tuple[dict, object, object, dict]:
    fit, calibration = _split_fit_calibration(train)
    X_fit, cols = get_model_features(fit, FEATURE_COLS_GAME)
    weights = season_recency_weights(fit["season"], reference_season=int(train["season"].max()))
    base_models = train_ensemble(X_fit, fit["target"].astype(int), weights)

    X_cal = calibration.reindex(columns=cols, fill_value=0.0).astype(float)
    calibrated_models = calibrate_models(base_models, X_cal, calibration["target"].astype(int))

    margin_model = train_margin_model(fit.reset_index(drop=True), FEATURE_COLS_MARGIN, weights)
    total_model = train_totals_model(fit.reset_index(drop=True), FEATURE_COLS_TOTALS, weights)

    numeric_calibration = calibration.select_dtypes(include=[np.number]).fillna(0)
    margin_pred = margin_model.predict(align_model_input(margin_model, numeric_calibration))
    total_pred = total_model.predict(align_model_input(total_model, numeric_calibration))
    margin_cal = DistributionCalibrator.fit("margin", calibration["margin"], margin_pred)
    total_cal = DistributionCalibrator.fit("total_points", calibration["total_points"], total_pred)
    bundle = {
        "base_models": base_models,
        "calibrated_models": calibrated_models,
        "margin_calibrator": margin_cal,
        "total_calibrator": total_cal,
        "feature_cols": cols,
        "fit_rows": len(fit),
        "calibration_rows": len(calibration),
    }
    return calibrated_models, margin_model, total_model, bundle


def _score_candidate(
    models: dict,
    margin_model,
    total_model,
    bundle: dict,
    test: pd.DataFrame,
) -> dict:
    if test.empty:
        return {}
    X = test.reindex(columns=bundle["feature_cols"], fill_value=0.0).astype(float)
    win_probs = ensemble_predict_proba(models, X)
    win = evaluate_model(test["target"].astype(int), win_probs)
    win["n_test"] = int(len(test))

    margin_X = align_model_input(margin_model, test.select_dtypes(include=[np.number]).fillna(0))
    total_X = align_model_input(total_model, test.select_dtypes(include=[np.number]).fillna(0))
    margin_pred = margin_model.predict(margin_X)
    total_pred = total_model.predict(total_X)
    margin = evaluate_distribution(test["margin"], margin_pred, bundle["margin_calibrator"])
    totals = evaluate_distribution(test["total_points"], total_pred, bundle["total_calibrator"])
    calibrated_margin = bundle["margin_calibrator"].predict(margin_pred)["mean"]
    calibrated_total = bundle["total_calibrator"].predict(total_pred)["mean"]
    return {
        "win_model": win,
        "winner_calibration": calibration_report(test["target"].astype(int), win_probs),
        "margin_distribution": margin,
        "total_distribution": totals,
        "win_probabilities": win_probs,
        "margin_predictions": calibrated_margin,
        "total_predictions": calibrated_total,
    }


def _baseline_metrics(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    if test.empty:
        return {}
    efficiency_prob = 1.0 / (1.0 + np.exp(-2.0 * pd.to_numeric(test.get("win_pct_diff", 0), errors="coerce").fillna(0)))
    efficiency = evaluate_model(test["target"].astype(int), efficiency_prob.to_numpy())

    elo = EloSystem()
    games = train[["game_date", "home_team_id", "away_team_id", "home_points", "away_points", "season"]].rename(
        columns={"home_points": "home_score", "away_points": "away_score"}
    )
    elo.fit(games)
    elo_probs: list[float] = []
    for _, row in test.sort_values("game_date").iterrows():
        home_id, away_id = int(row["home_team_id"]), int(row["away_team_id"])
        elo_probs.append(elo.win_probability(home_id, away_id, True))
        elo.update(home_id, away_id, int(row["home_points"]), int(row["away_points"]))
    elo_metrics = evaluate_model(test.sort_values("game_date")["target"].astype(int), np.asarray(elo_probs))
    market = evaluate_market_baseline(test)
    return {"elo": elo_metrics, "simple_efficiency": efficiency, "market": market}


def _segment_performance(scored: pd.DataFrame) -> dict[str, list[dict]]:
    """Report the blueprint's WNBA context slices on the untouched holdout."""
    if scored.empty:
        return {}
    frame = scored.copy()
    home_travel = pd.to_numeric(frame.get("home_travel_miles", 0), errors="coerce").fillna(0)
    away_travel = pd.to_numeric(frame.get("away_travel_miles", 0), errors="coerce").fillna(0)
    frame["_travel"] = pd.cut(
        pd.concat([home_travel, away_travel], axis=1).max(axis=1),
        bins=[-np.inf, 250, 1000, np.inf], labels=["local", "regional", "long_haul"],
    ).astype(str)
    home_rest = pd.to_numeric(frame.get("home_rest_days", 3), errors="coerce").fillna(3)
    away_rest = pd.to_numeric(frame.get("away_rest_days", 3), errors="coerce").fillna(3)
    minimum_rest = pd.concat([home_rest, away_rest], axis=1).min(axis=1)
    frame["_rest"] = np.select([minimum_rest <= 1, minimum_rest <= 2], ["back_to_back", "short_rest"], default="normal_rest")
    home_cont = pd.to_numeric(frame.get("home_roster_continuity"), errors="coerce")
    away_cont = pd.to_numeric(frame.get("away_roster_continuity"), errors="coerce")
    minimum_cont = pd.concat([home_cont, away_cont], axis=1).min(axis=1)
    frame["_continuity"] = pd.cut(
        minimum_cont, bins=[-np.inf, 0.5, 0.75, np.inf], labels=["low", "medium", "high"]
    ).astype(str).replace("nan", "unknown")
    cup = pd.to_numeric(frame.get("is_commissioners_cup", 0), errors="coerce").fillna(0).astype(bool)
    playoff = pd.to_numeric(frame.get("is_playoff", 0), errors="coerce").fillna(0).astype(bool)
    frame["_phase"] = np.select([playoff, cup], ["playoffs", "commissioners_cup"], default="regular")
    home_source = frame.get("home_source", pd.Series("unknown", index=frame.index)).fillna("unknown").astype(str)
    away_source = frame.get("away_source", pd.Series("unknown", index=frame.index)).fillna("unknown").astype(str)
    frame["_source"] = np.where(home_source == away_source, home_source, home_source + "+" + away_source)

    output: dict[str, list[dict]] = {}
    for label, column in {
        "travel": "_travel", "rest": "_rest", "roster_continuity": "_continuity",
        "season_phase": "_phase", "data_source": "_source",
    }.items():
        records = []
        for value, group in frame.groupby(column, dropna=False):
            if group.empty:
                continue
            probabilities = np.clip(group["home_win_prob"].astype(float).to_numpy(), 1e-6, 1 - 1e-6)
            truth = group["target"].astype(int).to_numpy()
            records.append({
                "segment": str(value),
                "n": int(len(group)),
                "accuracy": round(float(np.mean((probabilities >= 0.5) == truth)), 4),
                "log_loss": round(float(-np.mean(truth * np.log(probabilities) + (1 - truth) * np.log(1 - probabilities))), 4),
                "brier_score": round(float(np.mean((probabilities - truth) ** 2)), 4),
                "margin_mae": round(float(np.mean(np.abs(group["margin"] - group["margin_prediction"]))), 3),
                "total_mae": round(float(np.mean(np.abs(group["total_points"] - group["total_prediction"]))), 3),
            })
        output[label] = records
    return output


def _line_bucket_metrics(test: pd.DataFrame, scored: dict) -> dict:
    result: dict[str, list[dict]] = {"spread": [], "total": []}
    if test.empty:
        return result
    for market, actual_col, pred_key, line_col in (
        ("spread", "margin", "margin_predictions", "market_spread"),
        ("total", "total_points", "total_predictions", "market_total"),
    ):
        if line_col not in test.columns:
            continue
        frame = test[[actual_col, line_col]].copy()
        frame["prediction"] = np.asarray(scored[pred_key])
        frame = frame.dropna()
        if frame.empty:
            continue
        frame["line_bucket"] = pd.cut(frame[line_col], bins=5, duplicates="drop")
        for bucket, group in frame.groupby("line_bucket", observed=True):
            result[market].append({
                "bucket": str(bucket),
                "n": int(len(group)),
                "mae": round(float(np.mean(np.abs(group[actual_col] - group["prediction"]))), 3),
            })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Train release-gated WNBA models")
    parser.add_argument("--seasons", default="", help="Comma-separated seasons; defaults through 2025")
    parser.add_argument("--suffix", default="latest", help="Artifact suffix")
    parser.add_argument("--holdout-season", type=int, default=2025)
    args = parser.parse_args()

    cfg = get_league_config()
    seasons = (
        [int(value) for value in args.seasons.split(",") if value.strip()]
        if args.seasons
        else list(range(cfg.historical_start, min(cfg.current_season - 1, args.holdout_season) + 1))
    )
    print(f"Building replay for seasons {seasons}; untouched holdout={args.holdout_season}", flush=True)
    data = build_dataset(seasons).dropna(subset=["target", "margin", "total_points"]).reset_index(drop=True)
    train = data[data["season"] < args.holdout_season].reset_index(drop=True)
    holdout = data[data["season"] == args.holdout_season].reset_index(drop=True)
    if train.empty:
        raise RuntimeError("No pre-holdout training rows available")

    print("Running expanding-season folds...", flush=True)
    folds = expanding_season_eval(train, feature_cols=FEATURE_COLS_GAME)
    print(folds.to_string(index=False), flush=True)

    audit_models, audit_margin, audit_total, audit_bundle = _fit_candidate(train)
    holdout_score = _score_candidate(audit_models, audit_margin, audit_total, audit_bundle, holdout)
    scored_holdout = holdout.copy()
    if holdout_score:
        scored_holdout["home_win_prob"] = holdout_score["win_probabilities"]
        scored_holdout["margin_prediction"] = holdout_score["margin_predictions"]
        scored_holdout["total_prediction"] = holdout_score["total_predictions"]
    baselines = _baseline_metrics(train, scored_holdout)
    line_buckets = _line_bucket_metrics(scored_holdout, holdout_score) if holdout_score else {"spread": [], "total": []}
    segments = _segment_performance(scored_holdout) if holdout_score else {}
    drift = drift_report(train, holdout, audit_bundle["feature_cols"]) if not holdout.empty else {
        "max_psi": 0.0, "warning_features": [], "suspended": False, "feature_psi": {},
    }

    # Once the untouched score is recorded, refit the 2026 shadow candidate on
    # every completed season, including 2025.
    final_models, final_margin, final_total, final_bundle = _fit_candidate(data)
    save_models(final_bundle["base_models"], args.suffix)
    save_calibrated_models(final_models, args.suffix)
    save_regression_model(final_margin, "margin", args.suffix)
    save_regression_model(final_total, "totals", args.suffix)
    save_distribution_calibrator(final_bundle["margin_calibrator"], "margin", args.suffix)
    save_distribution_calibrator(final_bundle["total_calibrator"], "totals", args.suffix)

    games = data[["game_date", "home_team_id", "away_team_id", "home_points", "away_points", "season"]].rename(
        columns={"home_points": "home_score", "away_points": "away_score"}
    )
    EloSystem().fit(games).save()

    reference_path = model_dir() / f"training_reference_{args.suffix}.parquet"
    data.reindex(columns=final_bundle["feature_cols"]).to_parquet(reference_path, index=False)

    ledger = ledger_summary()
    gate = release_gate(
        holdout_season=args.holdout_season if not holdout.empty else None,
        holdout_rows=len(holdout),
        priced_bets=ledger["priced_bets"],
        distinct_games=ledger["distinct_games"],
        priced_by_market=ledger["priced_by_market"],
        mean_clv=ledger["mean_clv"],
        drift_suspended=drift["suspended"],
    )
    holdout_public = {key: value for key, value in holdout_score.items() if not isinstance(value, np.ndarray)}
    metrics = {
        "artifact_status": gate["status"],
        "release_gate": gate,
        "win_model": holdout_public.get("win_model", {}),
        "holdout_2025": holdout_public,
        "winner_calibration": holdout_public.get("winner_calibration", {}),
        "walk_forward": folds.to_dict("records"),
        "baselines": baselines,
        "line_bucket_calibration": line_buckets,
        "segment_performance": segments,
        "drift": drift,
        "paper_ledger": ledger,
        "margin": holdout_public.get("margin_distribution", {}),
        "totals": holdout_public.get("total_distribution", {}),
        "n_rows": int(len(data)),
        "training_rows": int(len(train)),
        "holdout_rows": int(len(holdout)),
        "holdout_season": args.holdout_season,
        "seasons": sorted(int(value) for value in data["season"].unique()),
        "feature_cols": final_bundle["feature_cols"],
        "calibration": {
            "winner": "isotonic",
            "margin": final_bundle["margin_calibrator"].to_dict(),
            "total": final_bundle["total_calibrator"].to_dict(),
        },
        "replay_horizons": ["morning", "injury_report", "pre_tip"],
    }
    save_eval_metrics(metrics)
    metadata_path = model_dir() / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    metadata.update({
        "artifact_status": gate["status"],
        "release_gate": gate,
        "training_seasons": metrics["seasons"],
        "holdout_season": args.holdout_season,
        "feature_cols": final_bundle["feature_cols"],
        "distribution_calibration": True,
    })
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(gate, indent=2), flush=True)
    print(f"Artifacts -> {model_dir()}", flush=True)


if __name__ == "__main__":
    main()
