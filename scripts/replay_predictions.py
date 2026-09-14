"""Replay a completed WNBA season at three real-world information horizons."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_fetcher import get_schedule, load_odds_history, normalized_dir  # noqa: E402
from utils.evaluation import (  # noqa: E402
    attach_closing_lines,
    freeze_prediction_ledger,
    grade_ledger,
    load_bet_ledger,
    save_bet_ledger,
)
from utils.identity import get_team_by_canonical  # noqa: E402
from utils.prediction_engine import predict_season_games  # noqa: E402


def _horizons(start: pd.Timestamp) -> dict[str, pd.Timestamp]:
    start = start.tz_convert("UTC") if start.tzinfo else start.tz_localize("UTC")
    eastern = start.tz_convert("America/New_York")
    morning = eastern.normalize() + pd.Timedelta(hours=9)
    return {
        "morning": morning.tz_convert("UTC"),
        "injury_report": start - pd.Timedelta(hours=6),
        "pre_tip": start - pd.Timedelta(minutes=45),
    }


def _odds_as_of(history: pd.DataFrame, game_id: str, as_of: pd.Timestamp) -> pd.DataFrame:
    if history.empty:
        return history
    frame = history[history["canonical_game_id"].astype(str) == str(game_id)].copy()
    observed = pd.to_datetime(frame["retrieved_at"], errors="coerce", utc=True)
    frame = frame[observed <= as_of].assign(_observed=observed[observed <= as_of])
    keys = ["canonical_game_id", "book", "market", "name"]
    return frame.sort_values("_observed").drop_duplicates(keys, keep="last").drop(columns="_observed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay WNBA forecasts at morning/injury/pre-tip horizons")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--limit", type=int, default=0, help="Optional game limit for a smoke replay")
    args = parser.parse_args()

    schedule = get_schedule(args.season)
    completed = schedule[
        schedule["home_score"].notna() & schedule["away_score"].notna()
    ].sort_values("scheduled_start")
    if args.limit:
        completed = completed.head(args.limit)
    odds_history = load_odds_history()
    replay_frames: list[pd.DataFrame] = []
    for number, (_, game) in enumerate(completed.iterrows(), start=1):
        start = pd.to_datetime(game.get("scheduled_start"), errors="coerce", utc=True)
        if pd.isna(start):
            start = pd.to_datetime(game["game_date"], utc=True) + pd.Timedelta(hours=23)
        game_id = str(game["canonical_game_id"])
        for horizon, as_of in _horizons(start).items():
            odds = _odds_as_of(odds_history, game_id, as_of)
            prediction = predict_season_games(
                args.season,
                odds_df=odds,
                as_of=as_of.isoformat(),
                stage=horizon,
                game_ids={game_id},
            )
            if not prediction.empty:
                replay_frames.append(prediction)
                freeze_prediction_ledger(prediction, horizon=horizon, frozen_at=as_of.isoformat())
        if number % 25 == 0:
            print(f"Replayed {number}/{len(completed)} games", flush=True)

    if replay_frames:
        replay = pd.concat(replay_frames, ignore_index=True)
        out = normalized_dir().parent / "evaluation" / f"replay_{args.season}.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        replay.to_parquet(out, index=False)
        print(f"Replay rows: {len(replay)} -> {out}", flush=True)

    # Attach latest pre-tip/closing snapshots and grade finished decisions.
    closing = odds_history.copy()
    if not closing.empty:
        closing["_observed"] = pd.to_datetime(closing["retrieved_at"], errors="coerce", utc=True)
        keys = ["canonical_game_id", "book", "market", "name"]
        closing = closing.sort_values("_observed").drop_duplicates(keys, keep="last")
    graded_games = completed.copy()
    graded_games["home_team"] = graded_games["home_team_id"].apply(
        lambda value: (get_team_by_canonical(value) or {}).get("display_name", str(value))
    )
    graded_games["away_team"] = graded_games["away_team_id"].apply(
        lambda value: (get_team_by_canonical(value) or {}).get("display_name", str(value))
    )
    ledger = attach_closing_lines(load_bet_ledger(), closing)
    ledger = grade_ledger(ledger, graded_games)
    save_bet_ledger(ledger)
    print("Replay complete; ledger remains paper-only.", flush=True)


if __name__ == "__main__":
    main()
