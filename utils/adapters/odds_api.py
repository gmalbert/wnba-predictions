"""The Odds API adapter — WNBA moneylines, spreads, and totals.

Reads ODDS_API_KEY from the environment (see .env.example). Uses sport key
``basketball_wnba``. Snapshots are stored normalized to the canonical odds
schema; unmatched games are retained with no forced matching.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pandas as pd
import requests

from utils.adapters.base import SourceUnavailableError
from utils.data_contracts import ODDS_COLUMNS
from utils.league_config import get_league_config

_BASE = "https://api.the-odds-api.com/v4/sports/basketball_wnba/odds"
_TIMEOUT = 20
_SPORT_KEY = "basketball_wnba"

MARKETS = ["h2h", "spreads", "totals"]
REGIONS = "us"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _load_env_key() -> str:
    """Read ODDS_API_KEY from the environment or the repo .env file."""
    key = os.getenv("ODDS_API_KEY", "")
    if key:
        return key
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ODDS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


class OddsApiAdapter:
    """Adapter around The Odds API for WNBA markets."""

    source_name = "the_odds_api"

    def __init__(self, api_key: str | None = None) -> None:
        self.cfg = get_league_config()
        self.api_key = api_key or _load_env_key()

    def fetch_odds(self) -> pd.DataFrame:
        """Current WNBA odds across books, normalized to the canonical schema."""
        if not self.api_key:
            raise SourceUnavailableError("ODDS_API_KEY is not set")
        try:
            resp = requests.get(
                _BASE,
                params={
                    "apiKey": self.api_key,
                    "regions": REGIONS,
                    "markets": ",".join(MARKETS),
                    "oddsFormat": "american",
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            games = resp.json()
        except Exception as e:
            raise SourceUnavailableError(f"Odds API request failed: {e}") from e
        if not games:
            return pd.DataFrame(columns=ODDS_COLUMNS)

        rows = []
        for game in games:
            game_id = game.get("id", "")
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            commence = game.get("commence_time", "")
            for bm in game.get("bookmakers", []):
                book = bm.get("key", "")
                for market in bm.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        rows.append({
                            "league_key": self.cfg.league_key,
                            "season": None,
                            "canonical_game_id": game_id,
                            "game_date": commence[:10] if commence else None,
                            "home_team": home,
                            "away_team": away,
                            "book": book,
                            "market": market.get("key", ""),
                            "name": outcome.get("name", ""),
                            "price": outcome.get("price"),
                            "point": outcome.get("point"),
                            "commence_time": commence,
                            "source": self.source_name,
                            "retrieved_at": _now(),
                        })
        return pd.DataFrame(rows, columns=ODDS_COLUMNS)

    def fetch_schedule(self, date_from: str, date_to: str) -> pd.DataFrame:
        raise SourceUnavailableError("Odds API is not a schedule source.")

    def fetch_team_game_stats(self, season: int) -> pd.DataFrame:
        raise SourceUnavailableError("Odds API is not a stats source.")

    def fetch_player_game_stats(self, season: int) -> pd.DataFrame:
        raise SourceUnavailableError("Odds API is not a stats source.")
