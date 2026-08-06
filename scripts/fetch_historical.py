"""Fetch and normalize historical WNBA data (wehoop primary, ESPN fallback).

Stages: fetch raw → validate → normalize → deduplicate → save partitioned.

Run: python scripts/fetch_historical.py [--seasons 2017,2018,...] [--force]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_fetcher import (  # noqa: E402
    get_player_game_stats,
    get_team_game_stats,
    normalized_dir,
)
from utils.league_config import get_league_config  # noqa: E402


def fetch_season(season: int, force: bool = False) -> dict:
    """Fetch team + player game stats for a season. Returns row counts."""
    print(f"[{season}] team game stats...", flush=True)
    tg = get_team_game_stats(season, force_refresh=force)
    print(f"[{season}] team rows: {len(tg)}", flush=True)

    print(f"[{season}] player game stats...", flush=True)
    pg = get_player_game_stats(season, force_refresh=force)
    print(f"[{season}] player rows: {len(pg)}", flush=True)

    return {"season": season, "team_rows": len(tg), "player_rows": len(pg)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch + normalize WNBA historical data")
    parser.add_argument("--seasons", default="", help="Comma-separated seasons (default: config historical_seasons)")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if cached")
    args = parser.parse_args()

    cfg = get_league_config()
    if args.seasons:
        seasons = [int(s) for s in args.seasons.split(",") if s.strip()]
    else:
        # Default: a few recent seasons for a fast baseline; override for full backfill
        seasons = [cfg.current_season - 2, cfg.current_season - 1, cfg.current_season]

    print(f"Seasons: {seasons}", flush=True)
    report = []
    for season in seasons:
        try:
            report.append(fetch_season(season, force=args.force))
        except Exception as e:
            print(f"[{season}] ERROR: {e}", file=sys.stderr, flush=True)
            report.append({"season": season, "error": str(e)})

    # Write a completeness report
    out = normalized_dir() / "completeness_report.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(report).to_csv(out, index=False)
    print(f"Completeness report -> {out}", flush=True)


if __name__ == "__main__":
    main()
