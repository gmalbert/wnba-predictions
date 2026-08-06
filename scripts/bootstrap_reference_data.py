"""Seed the canonical WNBA team reference table.

Builds data_files/wnba/reference/teams.parquet from the current league roster
(ESPN teams endpoint + wehoop schedule/box identifiers). Player identity is
seeded from wehoop player box scores.

Run: python scripts/bootstrap_reference_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_contracts import TEAMS_COLUMNS, PLAYERS_COLUMNS  # noqa: E402
from utils.identity import reference_dir, refresh_all_caches  # noqa: E402
from utils.league_config import get_league_config  # noqa: E402


def build_teams_table() -> pd.DataFrame:
    """Build the canonical teams table from ESPN + wehoop identifiers."""
    cfg = get_league_config()

    rows: list[dict] = []
    try:
        from utils.adapters.espn import EspnAdapter

        espn = EspnAdapter()
        teams = espn.fetch_rosters(cfg.current_season)  # reuses team list endpoint
        # fetch_rosters returns per-player rows; group by team for team metadata
        if not teams.empty:
            for _, grp in teams.groupby("team_id"):
                tid = int(grp["team_id"].iloc[0])
                name = str(grp["team_name"].iloc[0])
                abbr = name
                # Infer abbreviation from name (e.g. "Las Vegas Aces" -> "LV")
                words = name.split()
                abbr = "".join(w[0] for w in words[:2]).upper() if len(words) >= 2 else name[:3].upper()
                rows.append({
                    "canonical_team_id": tid,
                    "canonical_franchise_id": tid,
                    "display_name": name,
                    "city": words[0] if words else "",
                    "nickname": " ".join(words[1:]) if len(words) > 1 else name,
                    "abbreviation": abbr,
                    "conference": "",
                    "active_from": cfg.historical_start,
                    "active_to": cfg.current_season,
                    "venue": "",
                    "latitude": None,
                    "longitude": None,
                    "wnba_stats_team_id": None,
                    "espn_team_id": tid,
                    "balldontlie_team_id": None,
                    "basketball_reference_slug": "",
                    "wehoop_team_id": tid,
                })
    except Exception as e:
        print(f"WARN: could not seed teams from ESPN: {e}", file=sys.stderr)

    df = pd.DataFrame(rows, columns=TEAMS_COLUMNS)
    # De-dup by canonical id, keeping first
    df = df.drop_duplicates("canonical_team_id", keep="first")
    return df


def build_players_table(seasons: list[int] | None = None) -> pd.DataFrame:
    """Seed player identity from wehoop player box scores."""
    cfg = get_league_config()
    seasons = seasons or [cfg.current_season, cfg.current_season - 1]

    records: list[dict] = []
    try:
        from utils.adapters.wehoop import _PLAYER_BOX_URL, _read_season

        for season in seasons:
            box = _read_season(_PLAYER_BOX_URL, season)
            if box.empty:
                continue
            for _, r in box.iterrows():
                pid = r.get("athlete_id")
                if pid is None:
                    continue
                records.append({
                    "canonical_player_id": int(pid),
                    "display_name": str(r.get("athlete_display_name", "")),
                    "normalized_name": "",
                    "birth_date": None,
                    "active_from": min(seasons),
                    "active_to": cfg.current_season,
                    "wnba_stats_player_id": None,
                    "espn_player_id": int(pid),
                    "balldontlie_player_id": None,
                    "basketball_reference_slug": "",
                })
    except Exception as e:
        print(f"WARN: could not seed players from wehoop: {e}", file=sys.stderr)

    df = pd.DataFrame(records, columns=PLAYERS_COLUMNS)
    df = df.drop_duplicates("canonical_player_id", keep="first")
    return df


def main() -> None:
    cfg = get_league_config()
    out = reference_dir()
    out.mkdir(parents=True, exist_ok=True)

    teams = build_teams_table()
    if not teams.empty:
        teams.to_parquet(out / "teams.parquet", index=False)
        print(f"Wrote {len(teams)} teams -> {out / 'teams.parquet'}")
    else:
        print("WARN: teams table empty; no reference written")

    players = build_players_table()
    if not players.empty:
        players.to_parquet(out / "players.parquet", index=False)
        print(f"Wrote {len(players)} players -> {out / 'players.parquet'}")
    else:
        print("WARN: players table empty; no reference written")

    refresh_all_caches()
    print("Reference caches refreshed.")


if __name__ == "__main__":
    main()
