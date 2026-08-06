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
    get_player_game_stats(season, force_refresh=True)

    # 2. Generate predictions
    print("Generating predictions...", flush=True)
    df = generate_and_store_predictions(season)
    print(f"Predictions: {len(df)}", flush=True)

    # 3. Health report
    import subprocess
    subprocess.run([sys.executable, str(ROOT / "scripts" / "publish_data_health.py")], check=False)

    print("Daily update complete.")


if __name__ == "__main__":
    main()
