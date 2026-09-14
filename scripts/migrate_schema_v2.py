"""Migrate cached normalized WNBA partitions to canonical schema v2."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_contracts import GAMES_COLUMNS, INJURIES_COLUMNS, ODDS_COLUMNS, PLAYER_GAME_COLUMNS, TEAM_GAME_COLUMNS  # noqa: E402
from utils.identity import load_teams  # noqa: E402
from utils.league_config import get_league_config  # noqa: E402


def _source_team_map() -> dict[int, int]:
    teams = load_teams()
    return {
        int(row["wnba_stats_team_id"]): int(row["canonical_team_id"])
        for row in teams.to_dict("records")
        if pd.notna(row.get("wnba_stats_team_id")) and pd.notna(row.get("canonical_team_id"))
    }


def _migrate(path: Path, columns: list[str], team_columns: list[str], mapping: dict[int, int]) -> int:
    try:
        frame = pd.read_parquet(path)
    except Exception:
        return 0
    for column in team_columns:
        if column in frame.columns:
            numeric = pd.to_numeric(frame[column], errors="coerce")
            mapped = numeric.map(mapping)
            frame[column] = mapped.where(mapped.notna(), numeric).round().astype("Int64")
    frame.reindex(columns=columns).to_parquet(path, index=False)
    return len(frame)


def _game_key(group: pd.DataFrame) -> str | None:
    teams = sorted(
        str(int(value))
        for value in pd.to_numeric(group["canonical_team_id"], errors="coerce").dropna().unique()
    )
    dates = pd.to_datetime(group.get("game_date"), errors="coerce").dropna()
    if len(teams) != 2 or dates.empty:
        return None
    return f"{dates.iloc[0].date().isoformat()}|{'|'.join(teams)}"


def _align_player_game_ids(root: Path) -> int:
    """Join cross-source game IDs by date and the canonical two-team pair."""
    aligned_rows = 0
    for player_path in root.glob("player_game_stats/season=*/player_game_stats.parquet"):
        season_part = player_path.parent.name
        team_path = root / "team_game_stats" / season_part / "team_game_stats.parquet"
        if not team_path.exists():
            continue
        players = pd.read_parquet(player_path)
        teams = pd.read_parquet(team_path)
        target_ids: dict[str, str] = {}
        for game_id, group in teams.groupby("canonical_game_id"):
            key = _game_key(group)
            if key:
                target_ids[key] = str(game_id)
        replacements: dict[str, str] = {}
        opponents: dict[tuple[str, int], int] = {}
        for source_game_id, group in players.groupby("canonical_game_id"):
            key = _game_key(group)
            if key and key in target_ids:
                replacements[str(source_game_id)] = target_ids[key]
            team_ids = [
                int(value)
                for value in pd.to_numeric(group["canonical_team_id"], errors="coerce").dropna().unique()
            ]
            if len(team_ids) == 2:
                opponents[(str(source_game_id), team_ids[0])] = team_ids[1]
                opponents[(str(source_game_id), team_ids[1])] = team_ids[0]
        source_ids = players["canonical_game_id"].astype(str)
        team_ids = pd.to_numeric(players["canonical_team_id"], errors="coerce").astype("Int64")
        players["opponent_team_id"] = [
            opponents.get((source_id, int(team_id))) if pd.notna(team_id) else None
            for source_id, team_id in zip(source_ids, team_ids)
        ]
        players["canonical_game_id"] = source_ids.map(replacements).fillna(source_ids)
        players.reindex(columns=PLAYER_GAME_COLUMNS).to_parquet(player_path, index=False)
        aligned_rows += int(source_ids.isin(replacements).sum())
    return aligned_rows


def main() -> None:
    root = get_league_config().storage_namespace("normalized")
    mapping = _source_team_map()
    migrated = []
    patterns = [
        ("games/season=*/games.parquet", GAMES_COLUMNS, ["home_team_id", "away_team_id"]),
        ("team_game_stats/season=*/team_game_stats.parquet", TEAM_GAME_COLUMNS, ["canonical_team_id", "opponent_team_id"]),
        ("player_game_stats/season=*/player_game_stats.parquet", PLAYER_GAME_COLUMNS, ["canonical_team_id", "opponent_team_id"]),
        ("injuries/*.parquet", INJURIES_COLUMNS, ["canonical_team_id"]),
        ("odds/*.parquet", ODDS_COLUMNS, []),
    ]
    for pattern, columns, team_columns in patterns:
        for path in root.glob(pattern):
            rows = _migrate(path, columns, team_columns, mapping)
            migrated.append({"path": str(path.relative_to(root)), "rows": rows})
            print(f"{path.relative_to(root)}: {rows} rows")
    aligned = _align_player_game_ids(root)
    print(f"Aligned {aligned} player rows to canonical cross-source game IDs.")
    print(f"Migrated {len(migrated)} normalized files to schema v2.")


if __name__ == "__main__":
    main()
