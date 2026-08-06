"""Train baseline WNBA win/margin/total models with chronological validation.

Run: python scripts/train_models.py [--seasons 2017,2018,...] [--suffix v1]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_fetcher import get_team_game_stats  # noqa: E402
from utils.feature_engine import build_training_dataset  # noqa: E402
from utils.league_config import get_league_config  # noqa: E402
from utils.model_utils import (  # noqa: E402
    FEATURE_COLS_GAME,
    EloSystem,
    calibrate_models,
    ensemble_predict_proba,
    evaluate_model,
    get_model_features,
    load_calibrated_models,
    model_dir,
    save_calibrated_models,
    save_eval_metrics,
    save_models,
    train_ensemble,
    train_margin_model,
    train_totals_model,
    evaluate_regression,
    save_regression_model,
    walk_forward_eval,
)


def build_dataset(seasons: list[int]) -> pd.DataFrame:
    """Concatenate training datasets across seasons (chronological)."""
    frames = []
    for season in seasons:
        tg = get_team_game_stats(season)
        if tg.empty:
            continue
        df = build_training_dataset(tg)
        if not df.empty:
            df["season"] = season
            frames.append(df)
        print(f"[{season}] training rows: {len(df)}", flush=True)
    if not frames:
        raise RuntimeError("No training data available")
    return pd.concat(frames, ignore_index=True).sort_values("game_date").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train WNBA baseline models")
    parser.add_argument("--seasons", default="", help="Comma-separated seasons (default: config historical range)")
    parser.add_argument("--suffix", default="latest", help="Artifact suffix")
    args = parser.parse_args()

    cfg = get_league_config()
    if args.seasons:
        seasons = [int(s) for s in args.seasons.split(",") if s.strip()]
    else:
        seasons = list(range(cfg.historical_start, cfg.current_season + 1))

    print("Building training dataset...", flush=True)
    df = build_dataset(seasons)
    df = df.dropna(subset=["target"]).reset_index(drop=True)
    print(f"Total training rows: {len(df)}", flush=True)

    # ── Walk-forward evaluation ───────────────────────────────────────────────
    print("Walk-forward evaluation...", flush=True)
    wf = walk_forward_eval(df, n_splits=min(5, max(2, len(df) // 200)))
    print(wf.to_string(index=False), flush=True)

    # ── Win model ─────────────────────────────────────────────────────────────
    print("Training win ensemble...", flush=True)
    X, cols = get_model_features(df, FEATURE_COLS_GAME)
    y = df["target"]
    split = int(len(df) * 0.8)
    X_tr, X_te = X.iloc[:split], X.iloc[split:]
    y_tr, y_te = y.iloc[:split], y.iloc[split:]
    models = train_ensemble(X_tr, y_tr)
    probs = ensemble_predict_proba(models, X_te)
    metrics = evaluate_model(y_te, probs)
    print(f"Win model: {metrics}", flush=True)

    # Calibrate on the last 20% held out
    print("Calibrating...", flush=True)
    cal_models = calibrate_models(models, X_te, y_te)
    save_models(models, args.suffix)
    save_calibrated_models(cal_models, args.suffix)

    # ── Margin + total models ─────────────────────────────────────────────────
    print("Training margin model...", flush=True)
    margin_model = train_margin_model(df)
    m_metrics = evaluate_regression(margin_model, df.iloc[split:], "margin")
    print(f"Margin model: {m_metrics}", flush=True)

    print("Training totals model...", flush=True)
    totals_model = train_totals_model(df)
    t_metrics = evaluate_regression(totals_model, df.iloc[split:], "total_points")
    print(f"Totals model: {t_metrics}", flush=True)

    save_regression_model(margin_model, "margin", args.suffix)
    save_regression_model(totals_model, "totals", args.suffix)

    # ── Elo ───────────────────────────────────────────────────────────────────
    print("Fitting Elo...", flush=True)
    games = df.rename(columns={
        "home_team_id": "home_team_id",
        "away_team_id": "away_team_id",
        "home_points": "home_score",
        "away_points": "away_score",
        "game_date": "game_date",
    })[["game_date", "home_team_id", "away_team_id", "home_score", "away_score", "season"]]
    elo = EloSystem().fit(games)
    elo.save()

    # ── Persist metrics ───────────────────────────────────────────────────────
    eval_metrics = {
        "win_model": metrics,
        "walk_forward": wf.to_dict("records"),
        "margin": m_metrics,
        "totals": t_metrics,
        "n_rows": int(len(df)),
        "seasons": seasons,
        "feature_cols": cols,
    }
    save_eval_metrics(eval_metrics)
    print(f"\nArtifacts -> {model_dir()}", flush=True)
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
