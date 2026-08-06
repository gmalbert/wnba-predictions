"""WNBA Stats adapter — official stats via the nba_api wrapper (league_id="10").

nba_api is used as an HTTP wrapper around stats.wnba.com endpoints. Where the
wrapper does not expose a needed parameter, we fall back to direct HTTP calls
with the same headers nba_api uses.
"""

from __future__ import annotations

import datetime as dt
import time

import pandas as pd

from utils.adapters.base import SourceUnavailableError
from utils.data_contracts import GAMES_COLUMNS, TEAM_GAME_COLUMNS, PLAYER_GAME_COLUMNS
from utils.league_config import get_league_config

_RATE_LIMIT_DELAY = 0.7


def _sleep() -> None:
    time.sleep(_RATE_LIMIT_DELAY)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class WnbaStatsAdapter:
    """Adapter around nba_api endpoints configured for the WNBA."""

    source_name = "wnba_stats"

    def __init__(self) -> None:
        self.cfg = get_league_config()
        try:
            from nba_api.stats.endpoints import (  # noqa: F401 - import check
                scoreboardv3,
                leaguegamelog,
                leaguestandingsv3,
                commonteamroster,
                leaguedashteamstats,
                leaguedashplayerstats,
            )
            self._ok = True
        except Exception as e:  # pragma: no cover
            self._ok = False
            self._import_error = e

    def _require(self) -> None:
        if not self._ok:
            raise SourceUnavailableError(f"nba_api import failed: {self._import_error}")

    def _season_str(self, season: int) -> str:
        return self.cfg.normalize_season(str(season))

    # ── Scoreboard / schedule ─────────────────────────────────────────────────

    def fetch_schedule(self, date_from: str, date_to: str) -> pd.DataFrame:
        self._require()
        from nba_api.stats.endpoints import scoreboardv3

        rows = []
        d = dt.date.fromisoformat(date_from)
        end = dt.date.fromisoformat(date_to)
        while d <= end:
            _sleep()
            try:
                sb = scoreboardv3.ScoreboardV3(
                    game_date=d.strftime("%m/%d/%Y"),
                    league_id=self.cfg.stats_league_id,
                )
            except Exception as e:
                raise SourceUnavailableError(f"ScoreboardV3 failed: {e}") from e
            games = sb.data_sets[1].get_data_frame() if len(sb.data_sets) > 1 else None
            teams = sb.data_sets[2].get_data_frame() if len(sb.data_sets) > 2 else None
            if games is None or teams is None or games.empty:
                d += dt.timedelta(days=1)
                continue
            tricode_to_id = dict(zip(teams["teamTricode"], teams["teamId"]))
            tricode_to_name = {
                r["teamTricode"]: f"{r['teamCity']} {r['teamName']}"
                for _, r in teams.iterrows()
            }
            for _, g in games.iterrows():
                code = str(g.get("gameCode", ""))
                parts = code.split("/")
                if len(parts) == 2 and len(parts[1]) == 6:
                    away_abbr, home_abbr = parts[1][:3], parts[1][3:]
                else:
                    continue
                rows.append({
                    "league_key": self.cfg.league_key,
                    "season": None,
                    "season_type": None,
                    "canonical_game_id": str(g.get("gameId", "")),
                    "source_game_id": str(g.get("gameId", "")),
                    "game_date": d.isoformat(),
                    "scheduled_start": g.get("gameTimeUTC"),
                    "home_team_id": tricode_to_id.get(home_abbr),
                    "away_team_id": tricode_to_id.get(away_abbr),
                    "home_score": None,
                    "away_score": None,
                    "status": g.get("gameStatusText", ""),
                    "neutral_site": False,
                    "overtime_periods": None,
                    "source": self.source_name,
                    "retrieved_at": _now(),
                })
            d += dt.timedelta(days=1)
        return pd.DataFrame(rows, columns=GAMES_COLUMNS)

    # ── League game logs ──────────────────────────────────────────────────────

    def fetch_team_game_stats(self, season: int) -> pd.DataFrame:
        """Team-level game log for a season (LeagueGameLog player_or_team='T')."""
        self._require()
        from nba_api.stats.endpoints import leaguegamelog

        _sleep()
        try:
            raw = leaguegamelog.LeagueGameLog(
                season=self._season_str(season),
                season_type_all_star=self.cfg.default_season_type,
                player_or_team_abbreviation="T",
                league_id_nullable=self.cfg.stats_league_id,
            )
            df = raw.get_data_frames()[0]
        except Exception as e:
            raise SourceUnavailableError(f"LeagueGameLog failed: {e}") from e
        if df.empty:
            raise SourceUnavailableError("LeagueGameLog returned no rows")

        df = df.copy()
        rows = []
        for _, r in df.iterrows():
            matchup = str(r.get("MATCHUP", ""))
            is_home = 1 if "vs." in matchup else 0
            rows.append({
                "league_key": self.cfg.league_key,
                "season": int(season),
                "season_type": self.cfg.default_season_type,
                "canonical_game_id": str(r.get("GAME_ID", "")),
                "canonical_team_id": int(r.get("TEAM_ID", 0)),
                "opponent_team_id": None,
                "is_home": is_home,
                "game_date": str(r.get("GAME_DATE", ""))[:10],
                "win": 1 if r.get("WL") == "W" else 0,
                "points": r.get("PTS"),
                "field_goals_made": r.get("FGM"),
                "field_goals_attempted": r.get("FGA"),
                "three_points_made": r.get("FG3M"),
                "three_points_attempted": r.get("FG3A"),
                "free_throws_made": r.get("FTM"),
                "free_throws_attempted": r.get("FTA"),
                "offensive_rebounds": r.get("OREB"),
                "defensive_rebounds": r.get("DREB"),
                "assists": r.get("AST"),
                "turnovers": r.get("TOV"),
                "steals": r.get("STL"),
                "blocks": r.get("BLK"),
                "personal_fouls": r.get("PF"),
                "minutes": None,
                "possessions": None,
                "source": self.source_name,
                "retrieved_at": _now(),
            })
        return pd.DataFrame(rows, columns=TEAM_GAME_COLUMNS)

    def fetch_player_game_stats(self, season: int) -> pd.DataFrame:
        """Player-level game log for a season (LeagueGameLog player_or_team='P')."""
        self._require()
        from nba_api.stats.endpoints import leaguegamelog

        _sleep()
        try:
            raw = leaguegamelog.LeagueGameLog(
                season=self._season_str(season),
                season_type_all_star=self.cfg.default_season_type,
                player_or_team_abbreviation="P",
                league_id_nullable=self.cfg.stats_league_id,
            )
            df = raw.get_data_frames()[0]
        except Exception as e:
            raise SourceUnavailableError(f"LeagueGameLog(player) failed: {e}") from e
        if df.empty:
            raise SourceUnavailableError("LeagueGameLog(player) returned no rows")

        rows = []
        for _, r in df.iterrows():
            rows.append({
                "league_key": self.cfg.league_key,
                "season": int(season),
                "season_type": self.cfg.default_season_type,
                "canonical_game_id": str(r.get("GAME_ID", "")),
                "canonical_player_id": int(r.get("PLAYER_ID", 0)),
                "canonical_team_id": int(r.get("TEAM_ID", 0)),
                "started": None,
                "minutes": None,
                "points": r.get("PTS"),
                "rebounds": r.get("REB"),
                "assists": r.get("AST"),
                "steals": r.get("STL"),
                "blocks": r.get("BLK"),
                "turnovers": r.get("TOV"),
                "field_goals_made": r.get("FGM"),
                "field_goals_attempted": r.get("FGA"),
                "three_points_made": r.get("FG3M"),
                "three_points_attempted": r.get("FG3A"),
                "free_throws_made": r.get("FTM"),
                "free_throws_attempted": r.get("FTA"),
                "source": self.source_name,
                "retrieved_at": _now(),
            })
        return pd.DataFrame(rows, columns=PLAYER_GAME_COLUMNS)

    # ── Standings / rosters ───────────────────────────────────────────────────

    def fetch_standings(self, season: int) -> pd.DataFrame:
        self._require()
        from nba_api.stats.endpoints import leaguestandingsv3

        _sleep()
        try:
            raw = leaguestandingsv3.LeagueStandingsV3(
                season=self._season_str(season),
                league_id=self.cfg.stats_league_id,
            )
            df = raw.standings.get_data_frame()
        except Exception as e:
            raise SourceUnavailableError(f"LeagueStandingsV3 failed: {e}") from e
        if df.empty:
            raise SourceUnavailableError("LeagueStandingsV3 returned no rows")
        df = df.copy()
        df["season"] = int(season)
        return df

    def fetch_rosters(self, season: int) -> pd.DataFrame:
        self._require()
        from nba_api.stats.endpoints import commonteamroster
        from nba_api.stats.static import teams as nba_teams

        rows = []
        for t in nba_teams.get_teams():
            _sleep()
            try:
                raw = commonteamroster.CommonTeamRoster(
                    team_id=t["id"],
                    season=self._season_str(season),
                    league_id_nullable=self.cfg.stats_league_id,
                )
                df = raw.common_team_roster.get_data_frame()
            except Exception:
                continue
            if df.empty:
                continue
            for _, r in df.iterrows():
                rows.append({
                    "season": int(season),
                    "team_id": t["id"],
                    "team_name": t["full_name"],
                    "player_id": r.get("PLAYER_ID"),
                    "player_name": r.get("PLAYER"),
                    "position": r.get("POSITION"),
                    "jersey": r.get("NUM"),
                })
        return pd.DataFrame(rows)
