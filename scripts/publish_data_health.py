"""Publish a data health report from cached source data.

Run: python scripts/publish_data_health.py [--seasons 2025,2026]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_fetcher import (  # noqa: E402
    get_injuries,
    get_player_game_stats,
    get_schedule,
    get_team_game_stats,
    health_path,
    load_health,
)
from utils.league_config import get_league_config  # noqa: E402
from utils.quality import (  # noqa: E402
    check_freshness,
    check_games,
    check_injuries,
    check_player_games,
    check_team_games,
    summarize,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish WNBA data health report")
    parser.add_argument("--seasons", default="", help="Comma-separated seasons")
    args = parser.parse_args()

    cfg = get_league_config()
    if args.seasons:
        seasons = [int(s) for s in args.seasons.split(",") if s.strip()]
    else:
        seasons = [cfg.current_season]

    all_issues: list = []
    datasets: dict[str, pd.DataFrame] = {}
    for season in seasons:
        for name, loader in [
            ("games", get_schedule),
            ("team_game_stats", get_team_game_stats),
            ("player_game_stats", get_player_game_stats),
        ]:
            try:
                datasets[f"{name}_{season}"] = loader(season)
            except Exception:
                datasets[f"{name}_{season}"] = pd.DataFrame()

    injuries = get_injuries()
    datasets["injuries"] = injuries

    all_issues.extend(check_games(datasets.get(f"games_{seasons[-1]}")))
    all_issues.extend(check_team_games(datasets.get(f"team_game_stats_{seasons[-1]}")))
    all_issues.extend(check_player_games(datasets.get(f"player_game_stats_{seasons[-1]}")))
    all_issues.extend(check_injuries(injuries))
    all_issues.extend(check_freshness(datasets, {
        "games": 48, "team_game_stats": 48, "player_game_stats": 72, "injuries": 24,
    }))

    report = summarize(all_issues)
    report["sources"] = load_health()
    report["seasons"] = seasons
    report["published_at"] = pd.Timestamp.now(tz="UTC").isoformat()

    out = health_path().parent / "data_health_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Report -> {out}")
    print(f"healthy: {report['healthy']}  errors: {report['error_count']}  warnings: {report['warning_count']}")


if __name__ == "__main__":
    main()
