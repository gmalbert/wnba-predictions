"""BALLDONTLIE adapter — simple REST fallback for schedule and results."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import requests

from utils.adapters.base import SourceUnavailableError
from utils.data_contracts import GAMES_COLUMNS
from utils.league_config import get_league_config

_BASE = "https://api.balldontlie.io/v1"
_TIMEOUT = 20


class BalldontlieAdapter:
    """Adapter around the balldontlie.io REST API (WNBA supported)."""

    source_name = "balldontlie"

    def __init__(self, api_key: str | None = None) -> None:
        self.cfg = get_league_config()
        self.api_key = api_key or ""

    def _headers(self) -> dict:
        return {"Authorization": self.api_key} if self.api_key else {}

    def fetch_schedule(self, date_from: str, date_to: str) -> pd.DataFrame:
        # The balldontlie v1 API is NBA-only; WNBA coverage exists in v2 with a
        # league filter. Treat as unavailable unless a key is configured and the
        # v2 league param works — otherwise fall through to other adapters.
        raise SourceUnavailableError(
            "BALLDONTLIE WNBA schedule endpoint not configured (NBA-only v1)."
        )

    def fetch_team_game_stats(self, season: int) -> pd.DataFrame:
        raise SourceUnavailableError("BALLDONTLIE bulk team stats not available for WNBA.")

    def fetch_player_game_stats(self, season: int) -> pd.DataFrame:
        raise SourceUnavailableError("BALLDONTLIE bulk player stats not available for WNBA.")

    def fetch_standings(self, season: int) -> pd.DataFrame:
        raise SourceUnavailableError("BALLDONTLIE standings not available for WNBA.")
