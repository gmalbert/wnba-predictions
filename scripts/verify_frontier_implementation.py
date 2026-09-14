"""Assert persisted evidence for the audit/blueprint implementation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_contracts import PREDICTION_COLUMNS, validate_frame  # noqa: E402
from utils.data_fetcher import load_predictions, normalized_dir  # noqa: E402
from utils.model_utils import load_eval_metrics  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    metrics = load_eval_metrics()
    seasons = set(metrics.get("seasons", []))
    require({2023, 2024, 2025}.issubset(seasons), "Recent-season backfill is absent from artifact metadata")
    require(metrics.get("holdout_season") == 2025, "2025 is not the configured holdout")
    require(int(metrics.get("holdout_rows", 0)) > 0, "Untouched 2025 holdout has no rows")
    require(bool(metrics.get("winner_calibration", {}).get("bins")), "Winner calibration report is missing")
    require(metrics.get("margin", {}).get("crps") is not None, "Margin CRPS is missing")
    require(metrics.get("totals", {}).get("crps") is not None, "Total CRPS is missing")
    require(bool(metrics.get("walk_forward")), "Expanding-season folds are missing")
    required_segments = {"travel", "rest", "roster_continuity", "season_phase", "data_source"}
    require(required_segments.issubset(metrics.get("segment_performance", {})), "Context segment report is incomplete")
    gate = metrics.get("release_gate", {})
    require(set(gate.get("checks", {})) == {
        "untouched_2025_holdout", "minimum_300_priced_bets", "positive_clv", "drift_clear"
    }, "Production release gate checks are incomplete")

    for season in (2023, 2024, 2025):
        for kind, filename in (
            ("team_game_stats", "team_game_stats.parquet"),
            ("player_game_stats", "player_game_stats.parquet"),
        ):
            path = normalized_dir() / kind / f"season={season}" / filename
            require(path.exists(), f"Missing {season} {kind} partition")
            require(len(pd.read_parquet(path)) > 0, f"Empty {season} {kind} partition")

    predictions = load_predictions()
    validate_frame(predictions, PREDICTION_COLUMNS, "predictions")
    require(not predictions.empty, "Forward 2026 shadow ledger is empty")
    if gate.get("status") != "production_ready":
        require(predictions["paper_only"].fillna(False).all(), "Closed gate exposed a non-paper prediction")
        require(predictions["status"].eq("no_bet").all(), "Closed gate exposed a bet-ready prediction")
    rotation = json.loads(str(predictions.iloc[0]["availability_json"]))
    require(bool(rotation), "Rotation/minutes scenario payload is empty")
    print(
        "Frontier evidence passed: recent backfill, untouched holdout, calibration, "
        "context slices, release gate, shadow ledger, and rotation scenarios."
    )


if __name__ == "__main__":
    main()
