"""Run canonical edge-case fixtures required by the frontier blueprint."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_contracts import GAMES_COLUMNS, PLAYER_GAME_COLUMNS  # noqa: E402
from utils.quality import check_contract_fixture  # noqa: E402
from utils.scenario_engine import build_travel_context  # noqa: E402


def main() -> int:
    games = pd.DataFrame([
        {
            "league_key": "wnba", "season": 2026, "season_type": "Regular Season",
            "canonical_game_id": "postponed", "source_game_id": "p1", "game_date": "2026-06-01",
            "scheduled_start": "2026-06-01T23:00:00Z", "home_team_id": 1, "away_team_id": 2,
            "status": "STATUS_POSTPONED", "neutral_site": False, "season_phase": "regular",
            "source": "fixture", "retrieved_at": "2026-05-30T12:00:00Z",
        },
        {
            "league_key": "wnba", "season": 2026, "season_type": "Commissioner's Cup",
            "canonical_game_id": "neutral", "source_game_id": "n1", "game_date": "2026-06-03",
            "scheduled_start": "2026-06-03T16:00:00Z", "home_team_id": 1, "away_team_id": 99,
            "status": "STATUS_SCHEDULED", "neutral_site": True, "is_commissioners_cup": True,
            "season_phase": "commissioners_cup", "venue_latitude": 36.16, "venue_longitude": -86.78,
            "source": "fixture", "retrieved_at": "2026-05-30T12:00:00Z",
        },
    ]).reindex(columns=GAMES_COLUMNS)
    players = pd.DataFrame([
        {
            "league_key": "wnba", "season": 2026, "season_type": "Regular Season",
            "canonical_game_id": "neutral", "canonical_player_id": None, "canonical_team_id": 99,
            "game_date": "2026-06-03", "minutes": 0, "source": "fixture",
            "retrieved_at": "2026-06-03T18:00:00Z",
        }
    ]).reindex(columns=PLAYER_GAME_COLUMNS)
    issues = check_contract_fixture(games, "games") + check_contract_fixture(players, "player_game_stats")
    travel = build_travel_context(games)
    errors = [issue for issue in issues if issue.severity == "error"]
    if travel.empty or not bool(travel.loc[travel["canonical_game_id"] == "neutral", "neutral_site"].all()):
        print("ERROR: neutral-site travel context was not preserved")
        return 1
    for issue in issues:
        print(f"{issue.severity.upper()}: {issue.message}")
    if errors:
        return 1
    print("Contract fixtures passed: partial schedule, postponement, neutral site, expansion team, missing player ID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
