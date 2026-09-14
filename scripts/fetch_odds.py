"""Fetch WNBA odds snapshots from the configured odds providers.

Run: python scripts/fetch_odds.py [--force]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_fetcher import get_odds, get_prop_odds, normalized_dir  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch WNBA odds snapshot")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--horizon",
        choices=["latest", "morning", "injury_report", "midday", "pre_tip", "close"],
        default="latest",
    )
    parser.add_argument("--include-props", action="store_true", help="Snapshot supported player-prop markets")
    args = parser.parse_args()

    df = get_odds(force_refresh=args.force, snapshot_horizon=args.horizon)
    if df.empty:
        print("No odds returned (check ODDS_API_IO_KEY and THERUNDOWN_API_KEY).")
        sys.exit(0)
    print(f"Wrote {len(df)} odds rows -> {normalized_dir() / 'odds' / 'odds_latest.parquet'}")
    if args.include_props:
        event_ids = df["canonical_game_id"].dropna().astype(str).unique().tolist()
        props = get_prop_odds(event_ids, force_refresh=args.force, snapshot_horizon=args.horizon)
        print(f"Wrote {len(props)} player-prop odds rows")


if __name__ == "__main__":
    main()
