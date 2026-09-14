"""Generate and persist daily WNBA predictions.

Run: python scripts/generate_predictions.py [--season 2026]
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
    parser = argparse.ArgumentParser(description="Generate daily WNBA predictions")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument(
        "--stage",
        choices=["morning", "injury_report", "midday", "pre_tip", "close"],
        default="midday",
        help="As-of replay/snapshot horizon",
    )
    parser.add_argument("--as-of", default=None, help="UTC timestamp used for historical replay")
    args = parser.parse_args()

    cfg = get_league_config()
    season = args.season or cfg.current_season

    df = generate_and_store_predictions(season, stage=args.stage, as_of=args.as_of)
    if df.empty:
        print("No predictions generated (no upcoming games or insufficient data).")
        sys.exit(0)
    print(f"Wrote {len(df)} {args.stage} predictions for season {season}.")


if __name__ == "__main__":
    main()
