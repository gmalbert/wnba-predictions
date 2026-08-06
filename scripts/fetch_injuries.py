"""Fetch the latest WNBA injury report and cache it.

Run: python scripts/fetch_injuries.py [--force]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_fetcher import get_injuries, normalized_dir  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch WNBA injuries")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    df = get_injuries(force_refresh=args.force)
    if df.empty:
        print("No injuries returned.")
        sys.exit(0)
    print(f"Wrote {len(df)} injury rows -> {normalized_dir() / 'injuries' / 'injuries_latest.parquet'}")


if __name__ == "__main__":
    main()
