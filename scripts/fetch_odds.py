"""Fetch WNBA odds snapshots from The Odds API.

Run: python scripts/fetch_odds.py [--force]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_fetcher import get_odds, normalized_dir  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch WNBA odds snapshot")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    df = get_odds(force_refresh=args.force)
    if df.empty:
        print("No odds returned (check ODDS_API_KEY / season).")
        sys.exit(0)
    print(f"Wrote {len(df)} odds rows -> {normalized_dir() / 'odds' / 'odds_latest.parquet'}")


if __name__ == "__main__":
    main()
