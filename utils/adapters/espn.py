"""ESPN adapter — scoreboard, schedule, rosters, injuries, officials.

Uses ESPN's public JSON APIs for women's basketball (WNBA). All responses are
normalized to the canonical schemas in utils/data_contracts.py. Raw payloads
are preserved under data_files/raw/espn/ for schema-change diagnosis and
replaying parsers.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import requests

from utils.adapters.base import SourceUnavailableError
from utils.data_contracts import GAMES_COLUMNS, INJURIES_COLUMNS
from utils.league_config import get_league_config

_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba"
_TIMEOUT = 20


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _get(path: str, params: dict | None = None) -> dict:
    url = f"{_BASE}/{path}"
    try:
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise SourceUnavailableError(f"ESPN request failed ({url}): {e}") from e


def _save_raw(name: str, payload: dict) -> None:
    """Archive a raw ESPN payload under data_files/raw/espn/."""
    cfg = get_league_config()
    d = cfg.storage_namespace("raw", "espn")
    d.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = d / f"{name}_{stamp}.json"
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception:
        pass


class EspnAdapter:
    """Adapter around ESPN's public WNBA JSON endpoints."""

    source_name = "espn"

    def __init__(self) -> None:
        self.cfg = get_league_config()

    def fetch_schedule(self, date_from: str, date_to: str) -> pd.DataFrame:
        """Scoreboard/schedule for a date range (YYYY-MM-DD)."""
        rows = []
        d = dt.date.fromisoformat(date_from)
        end = dt.date.fromisoformat(date_to)
        while d <= end:
            data = _get("scoreboard", {"dates": d.strftime("%Y%m%d")})
            _save_raw(f"scoreboard_{d.strftime('%Y%m%d')}", data)
            for ev in data.get("events", []):
                comp = ev.get("competitions", [{}])[0]
                teams = comp.get("competitors", [])
                if len(teams) < 2:
                    continue
                home = next((t for t in teams if t.get("homeAway") == "home"), teams[0])
                away = next((t for t in teams if t.get("homeAway") == "away"), teams[1])
                status = comp.get("status", {}).get("type", {})
                rows.append({
                    "league_key": self.cfg.league_key,
                    "season": None,
                    "season_type": None,
                    "canonical_game_id": str(ev.get("id", "")),
                    "source_game_id": str(ev.get("id", "")),
                    "game_date": d.isoformat(),
                    "scheduled_start": ev.get("date"),
                    "home_team_id": int(home.get("id", 0)),
                    "away_team_id": int(away.get("id", 0)),
                    "home_score": home.get("score"),
                    "away_score": away.get("score"),
                    "status": status.get("name", ""),
                    "neutral_site": bool(comp.get("neutralSite", False)),
                    "overtime_periods": None,
                    "source": self.source_name,
                    "retrieved_at": _now(),
                })
            d += dt.timedelta(days=1)
        return pd.DataFrame(rows, columns=GAMES_COLUMNS)

    def fetch_team_game_stats(self, season: int) -> pd.DataFrame:
        # ESPN scoreboard per-day is inefficient for full seasons; the wehoop
        # adapter covers team box scores. This is a fallback that fans out to
        # team schedules.
        raise SourceUnavailableError(
            "ESPN adapter does not provide bulk team game stats; use wehoop or wnba_stats."
        )

    def fetch_player_game_stats(self, season: int) -> pd.DataFrame:
        raise SourceUnavailableError(
            "ESPN adapter does not provide bulk player game stats; use wehoop or wnba_stats."
        )

    def fetch_standings(self, season: int) -> pd.DataFrame:
        data = _get("standings")
        _save_raw(f"standings_{season}", data)
        rows = []
        for grp in data.get("children", []):
            conf = grp.get("name", "")
            for team in grp.get("standings", {}).get("entries", []):
                team_id = team.get("team", {}).get("id")
                stats = {s.get("name"): s.get("value") for s in team.get("stats", [])}
                rows.append({
                    "season": int(season),
                    "conference": conf,
                    "team_id": int(team_id) if team_id else None,
                    "team_name": team.get("team", {}).get("displayName", ""),
                    "wins": stats.get("wins"),
                    "losses": stats.get("losses"),
                    "win_pct": stats.get("winPercent"),
                    "games_behind": stats.get("gamesBehind"),
                    "streak": stats.get("streak"),
                    "home_record": stats.get("homeRecord"),
                    "road_record": stats.get("roadRecord"),
                })
        return pd.DataFrame(rows)

    def fetch_rosters(self, season: int) -> pd.DataFrame:
        """Fetch every WNBA team roster for a season via the ESPN team pages."""
        teams = _get("teams")
        rows = []
        for team in teams.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
            t = team.get("team", {})
            team_id = t.get("id")
            if not team_id:
                continue
            roster = _get(f"team/{team_id}/roster", {"season": season})
            _save_raw(f"roster_{team_id}_{season}", roster)
            for athlete in roster.get("athletes", []):
                rows.append({
                    "season": int(season),
                    "team_id": int(team_id),
                    "team_name": t.get("displayName", ""),
                    "player_id": athlete.get("id"),
                    "player_name": athlete.get("displayName", ""),
                    "position": athlete.get("position", {}).get("abbreviation", ""),
                    "jersey": athlete.get("jersey"),
                })
        return pd.DataFrame(rows)

    def fetch_injuries(self, as_of: str | None = None) -> pd.DataFrame:
        data = _get("injuries")
        _save_raw("injuries", data)
        rows = []
        for team_entry in data.get("injuries", []):
            team_name = team_entry.get("displayName", "")
            team_id = team_entry.get("team", {}).get("id")
            for inj in team_entry.get("injuries", []):
                athlete = inj.get("athlete", {})
                rows.append({
                    "league_key": self.cfg.league_key,
                    "canonical_player_id": athlete.get("id"),
                    "canonical_team_id": team_id,
                    "player_name": athlete.get("displayName", ""),
                    "team_name": team_name,
                    "status": inj.get("status", "Unknown"),
                    "description": inj.get("shortComment", inj.get("type", {}).get("description", "")),
                    "source": self.source_name,
                    "retrieved_at": _now(),
                })
        return pd.DataFrame(rows, columns=INJURIES_COLUMNS)

    def fetch_officials(self, date_from: str, date_to: str) -> pd.DataFrame:
        """Collect officials from event summaries for a date range."""
        rows = []
        d = dt.date.fromisoformat(date_from)
        end = dt.date.fromisoformat(date_to)
        while d <= end:
            data = _get("scoreboard", {"dates": d.strftime("%Y%m%d")})
            for ev in data.get("events", []):
                game_id = ev.get("id")
                try:
                    summary = _get(f"summary?event={game_id}")
                except SourceUnavailableError:
                    continue
                officials = summary.get("gameInfo", {}).get("officials", [])
                for off in officials:
                    rows.append({
                        "game_id": str(game_id),
                        "game_date": d.isoformat(),
                        "official_name": off.get("displayName", ""),
                        "official_position": off.get("position", {}).get("name", ""),
                        "source": self.source_name,
                    })
            d += dt.timedelta(days=1)
        return pd.DataFrame(rows)
