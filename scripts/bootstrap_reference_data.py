"""Seed the canonical WNBA team reference table.

Builds data_files/wnba/reference/teams.parquet from the current league roster
(ESPN teams endpoint + wehoop schedule/box identifiers). Player identity is
seeded from wehoop player box scores.

Run: python scripts/bootstrap_reference_data.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_contracts import TEAMS_COLUMNS, PLAYERS_COLUMNS  # noqa: E402
from utils.identity import reference_dir, refresh_all_caches  # noqa: E402
from utils.league_config import get_league_config  # noqa: E402


# Arena coordinates are stable reference inputs for approximate travel miles,
# not live venue assignments. Neutral-site games override these from schedule
# metadata. Expansion entries keep the table cold-start ready.
TEAM_METADATA = {
    "ATL": {"conference": "Eastern", "venue": "Gateway Center Arena", "latitude": 33.6457, "longitude": -84.4593},
    "CHI": {"conference": "Eastern", "venue": "Wintrust Arena", "latitude": 41.8537, "longitude": -87.6215},
    "CON": {"conference": "Eastern", "venue": "Mohegan Sun Arena", "latitude": 41.4911, "longitude": -72.0907},
    "DAL": {"conference": "Western", "venue": "College Park Center", "latitude": 32.7305, "longitude": -97.1079},
    "GSV": {"conference": "Western", "venue": "Chase Center", "latitude": 37.7680, "longitude": -122.3877, "active_from": 2025},
    "GS": {"conference": "Western", "venue": "Chase Center", "latitude": 37.7680, "longitude": -122.3877, "active_from": 2025},
    "IND": {"conference": "Eastern", "venue": "Gainbridge Fieldhouse", "latitude": 39.7639, "longitude": -86.1555},
    "LVA": {"conference": "Western", "venue": "Michelob ULTRA Arena", "latitude": 36.0909, "longitude": -115.1786},
    "LV": {"conference": "Western", "venue": "Michelob ULTRA Arena", "latitude": 36.0909, "longitude": -115.1786},
    "LAS": {"conference": "Western", "venue": "Crypto.com Arena", "latitude": 34.0430, "longitude": -118.2673},
    "LA": {"conference": "Western", "venue": "Crypto.com Arena", "latitude": 34.0430, "longitude": -118.2673},
    "MIN": {"conference": "Western", "venue": "Target Center", "latitude": 44.9795, "longitude": -93.2760},
    "NYL": {"conference": "Eastern", "venue": "Barclays Center", "latitude": 40.6826, "longitude": -73.9754},
    "NY": {"conference": "Eastern", "venue": "Barclays Center", "latitude": 40.6826, "longitude": -73.9754},
    "PHX": {"conference": "Western", "venue": "PHX Arena", "latitude": 33.4457, "longitude": -112.0712},
    "POR": {"conference": "Western", "venue": "Moda Center", "latitude": 45.5316, "longitude": -122.6668, "active_from": 2026},
    "SEA": {"conference": "Western", "venue": "Climate Pledge Arena", "latitude": 47.6221, "longitude": -122.3540},
    "TOR": {"conference": "Eastern", "venue": "Coca-Cola Coliseum", "latitude": 43.6356, "longitude": -79.4150, "active_from": 2026},
    "WAS": {"conference": "Eastern", "venue": "CareFirst Arena", "latitude": 38.8469, "longitude": -76.9919},
    "WSH": {"conference": "Eastern", "venue": "CareFirst Arena", "latitude": 38.8469, "longitude": -76.9919},
}


def apply_team_metadata(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    stats_ids: dict[str, int] = {}
    try:
        from nba_api.stats.static.teams import get_wnba_teams

        stats_ids = {str(team["full_name"]): int(team["id"]) for team in get_wnba_teams()}
    except Exception:
        pass
    for index, row in result.iterrows():
        metadata = TEAM_METADATA.get(str(row.get("abbreviation", "")).upper(), {})
        for column in ("conference", "venue", "latitude", "longitude", "active_from"):
            if column in metadata:
                result.at[index, column] = metadata[column]
        stats_id = stats_ids.get(str(row.get("display_name", "")))
        if stats_id is not None:
            result.at[index, "wnba_stats_team_id"] = stats_id
    return result.reindex(columns=TEAMS_COLUMNS)


def build_teams_table() -> pd.DataFrame:
    """Build the canonical teams table from ESPN + wehoop identifiers."""
    cfg = get_league_config()

    rows: list[dict] = []
    try:
        from utils.adapters.espn import EspnAdapter

        espn = EspnAdapter()
        teams = espn.fetch_teams()
        if not teams.empty:
            for _, t in teams.iterrows():
                tid = int(t["espn_team_id"])
                name = str(t["display_name"] or "")
                words = name.split()
                abbr = str(t.get("abbreviation") or "")
                if not abbr and len(words) >= 2:
                    abbr = "".join(w[0] for w in words[:2]).upper()
                rows.append({
                    "canonical_team_id": tid,
                    "canonical_franchise_id": tid,
                    "display_name": name,
                    "city": str(t.get("city") or (words[0] if words else "")),
                    "nickname": str(t.get("nickname") or (" ".join(words[1:]) if len(words) > 1 else name)),
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
    return apply_team_metadata(df)


def build_players_table(seasons: list[int] | None = None) -> pd.DataFrame:
    """Seed player identity from wehoop player box scores."""
    cfg = get_league_config()
    # wehoop-data coverage ends at 2022; use the most recent available seasons
    seasons = seasons or [2022, 2021]

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
    parser = argparse.ArgumentParser(description="Bootstrap or enrich WNBA canonical reference data")
    parser.add_argument("--enrich-only", action="store_true", help="Apply built-in arena/conference metadata without network access")
    args = parser.parse_args()
    cfg = get_league_config()
    out = reference_dir()
    out.mkdir(parents=True, exist_ok=True)

    existing_teams = out / "teams.parquet"
    teams = (
        apply_team_metadata(pd.read_parquet(existing_teams))
        if args.enrich_only and existing_teams.exists()
        else build_teams_table()
    )
    if not teams.empty:
        teams.to_parquet(out / "teams.parquet", index=False)
        print(f"Wrote {len(teams)} teams -> {out / 'teams.parquet'}")
    else:
        print("WARN: teams table empty; no reference written")

    if not args.enrich_only:
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
