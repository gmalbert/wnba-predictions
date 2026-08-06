"""Validate canonical data quality and print a report.

Run: python scripts/validate_data.py [--seasons 2025,2026]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_fetcher import get_team_game_stats, get_player_game_stats, get_schedule  # noqa: E402
from utils.league_config import get_league_config  # noqa: E402
from utils.quality import (  # noqa: E402
    check_freshness,
    check_games,
    check_odds,
    check_player_games,
    check_team_games,
    summarize,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate WNBA data quality")
    parser.add_argument("--seasons", default="", help="Comma-separated seasons")
    args = parser.parse_args()

    cfg = get_league_config()
    if args.seasons:
        seasons = [int(s) for s in args.seasons.split(",") if s.strip()]
    else:
        seasons = [cfg.current_season - 1, cfg.current_season]

    all_issues: list = []
    datasets: dict[str, pd.DataFrame] = {}

    for season in seasons:
        try:
            games = get_schedule(season)
            tg = get_team_game_stats(season)
            pg = get_player_game_stats(season)
        except Exception as e:
            print(f"[{season}] ERROR loading: {e}", file=sys.stderr)
            continue

        datasets[f"games_{season}"] = games
        datasets[f"team_game_{season}"] = tg
        datasets[f"player_game_{season}"] = pg

        all_issues.extend(check_games(games))
        all_issues.extend(check_team_games(tg))
        all_issues.extend(check_player_games(pg))
        print(f"[{season}] games={len(games)} team_rows={len(tg)} player_rows={len(pg)}", flush=True)

    all_issues.extend(check_odds(pd.DataFrame()))
    all_issues.extend(check_freshness(datasets, {}))

    report = summarize(all_issues)
    print("\n=== Data Quality Report ===")
    print(f"healthy: {report['healthy']}  errors: {report['error_count']}  warnings: {report['warning_count']}")
    for issue in report["issues"]:
        print(f"  [{issue['severity']}] {issue['check']}: {issue['message']}")

    sys.exit(0 if report["healthy"] else 1)


if __name__ == "__main__":
    main()
