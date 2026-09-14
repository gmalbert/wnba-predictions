"""One-shot daily update: data → validate → predictions → health report.

Run: python scripts/daily_update.py [--season 2026]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.league_config import get_league_config  # noqa: E402
from utils.prediction_engine import generate_and_store_predictions  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the daily WNBA update")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument(
        "--stage", choices=["morning", "injury_report", "midday", "pre_tip", "close"], default="midday"
    )
    args = parser.parse_args()

    cfg = get_league_config()
    season = args.season or cfg.current_season

    # 1. Refresh data (schedule, stats) — force to get newest results
    from utils.data_fetcher import get_schedule, get_team_game_stats, get_player_game_stats

    print("Refreshing schedule...", flush=True)
    get_schedule(season, force_refresh=True)
    print("Refreshing team stats...", flush=True)
    get_team_game_stats(season, force_refresh=True)
    print("Refreshing player stats...", flush=True)
    try:
        get_player_game_stats(season, force_refresh=True)
    except Exception as exc:
        print(f"Player stats unavailable; continuing with explicit uncertainty: {exc}", flush=True)

    # 2. Refresh market odds before generating the snapshot.
    from utils.data_fetcher import get_odds

    print("Refreshing odds...", flush=True)
    odds = get_odds(force_refresh=True, snapshot_horizon=args.stage)
    if odds.empty:
        print("Odds unavailable; predictions will show explicit market gaps.", flush=True)

    # 3. Generate predictions
    print("Generating predictions...", flush=True)
    df = generate_and_store_predictions(season, stage=args.stage)
    print(f"Predictions: {len(df)}", flush=True)

    # 4. Health report
    import subprocess
    subprocess.run([sys.executable, str(ROOT / "scripts" / "publish_data_health.py")], check=False)

    print("Daily update complete.")


if __name__ == "__main__":
    main()
