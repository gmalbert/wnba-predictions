"""TheRundown API v2 adapter for WNBA game markets."""

from __future__ import annotations

import datetime as dt
import os
from typing import Any

import pandas as pd
import requests

from utils.adapters.base import SourceUnavailableError
from utils.adapters.odds_common import empty_odds, load_env_key, now_utc, numeric_point, to_american
from utils.data_contracts import ODDS_COLUMNS
from utils.league_config import get_league_config

_BASE = "https://therundown.io/api/v2"
_SPORT_ID = 8  # WNBA
_TIMEOUT = 30
_DEFAULT_AFFILIATES = "19,23"  # DraftKings and FanDuel
_DEFAULT_MAX_REQUESTS = 10
_AFFILIATE_NAMES = {"2": "Bovada", "3": "Pinnacle", "19": "DraftKings", "22": "BetMGM", "23": "FanDuel", "24": "theScore Bet"}


def _events(payload: object) -> list[dict]:
    if isinstance(payload, dict) and isinstance(payload.get("events"), list):
        return [item for item in payload["events"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _team_names(event: dict) -> tuple[str, str]:
    teams = event.get("teams") or []
    if not isinstance(teams, list):
        return "", ""
    away = next((team for team in teams if str(team.get("home_away", team.get("homeAway", ""))).lower() == "away"), None)
    home = next((team for team in teams if str(team.get("home_away", team.get("homeAway", ""))).lower() == "home"), None)
    if away is None and teams:
        away = teams[0]
    if home is None and len(teams) > 1:
        home = teams[1]
    return str((away or {}).get("name", "")), str((home or {}).get("name", ""))


def _event_time(event: dict) -> str:
    schedule = event.get("schedule") or {}
    if isinstance(schedule, dict):
        return str(schedule.get("start_time") or schedule.get("start") or schedule.get("date") or "")
    return str(event.get("start_time") or event.get("date") or event.get("commence_time") or "")


class TheRundownAdapter:
    """Fetch WNBA core markets from TheRundown's date-based v2 API."""

    source_name = "therundown"

    def __init__(self, api_key: str | None = None) -> None:
        self.cfg = get_league_config()
        self.api_key = api_key or load_env_key("THERUNDOWN_API_KEY")
        self.affiliates = os.getenv("THERUNDOWN_AFFILIATE_IDS", _DEFAULT_AFFILIATES).strip()
        self.market_ids = os.getenv("THERUNDOWN_MARKET_IDS", "1,2,3").strip()
        try:
            self.max_requests = max(1, int(os.getenv("THERUNDOWN_MAX_REQUESTS", str(_DEFAULT_MAX_REQUESTS))))
        except ValueError:
            self.max_requests = _DEFAULT_MAX_REQUESTS
        self._request_count = 0
        try:
            self.lookahead_days = max(0, int(os.getenv("THERUNDOWN_LOOKAHEAD_DAYS", "7")))
        except ValueError:
            self.lookahead_days = 7

    def fetch_odds(self) -> pd.DataFrame:
        if not self.api_key:
            raise SourceUnavailableError("THERUNDOWN_API_KEY is not set")
        self._request_count = 0
        start = dt.datetime.now(dt.timezone.utc).date()
        rows: list[dict[str, Any]] = []
        for offset in range(self.lookahead_days + 1):
            date_value = start + dt.timedelta(days=offset)
            params: dict[str, object] = {
                "market_ids": self.market_ids,
                "main_line": "true",
            }
            if self.affiliates:
                params["affiliate_ids"] = self.affiliates
            try:
                payload = self._get(f"sports/{_SPORT_ID}/events/{date_value.isoformat()}", params)
            except SourceUnavailableError:
                raise
            for event in _events(payload):
                rows.extend(self._normalize_event(event))
        return pd.DataFrame(rows, columns=ODDS_COLUMNS) if rows else empty_odds()

    def _get(self, path: str, params: dict[str, object]) -> object:
        if self._request_count >= self.max_requests:
            raise SourceUnavailableError(
                f"TheRundown request budget exhausted ({self.max_requests}); stopped without retrying."
            )
        self._request_count += 1
        try:
            response = requests.get(
                f"{_BASE}/{path.lstrip('/')}",
                headers={"X-TheRundown-Key": self.api_key},
                params=params,
                timeout=_TIMEOUT,
            )
            if response.status_code == 429:
                raise SourceUnavailableError("TheRundown rate limit reached; stopped without retrying.")
            response.raise_for_status()
            return response.json()
        except SourceUnavailableError:
            raise
        except Exception as exc:
            raise SourceUnavailableError(f"TheRundown request failed: {exc}") from exc

    def _normalize_event(self, event: dict) -> list[dict[str, Any]]:
        event_id = str(event.get("event_id", event.get("id", "")))
        away, home = _team_names(event)
        commence = _event_time(event)
        retrieved = now_utc()
        rows: list[dict[str, Any]] = []
        for market in event.get("markets") or []:
            if not isinstance(market, dict):
                continue
            market_id = str(market.get("market_id", market.get("id", "")))
            canonical_market = {"1": "h2h", "2": "spreads", "3": "totals"}.get(market_id)
            if canonical_market is None:
                continue
            for participant in market.get("participants") or []:
                if not isinstance(participant, dict):
                    continue
                participant_name = str(participant.get("name", ""))
                for line in participant.get("lines") or []:
                    if not isinstance(line, dict):
                        continue
                    point = numeric_point(line.get("value", line.get("point", line.get("line"))))
                    prices = line.get("prices") or {}
                    if not isinstance(prices, dict):
                        continue
                    for affiliate_id, price_value in prices.items():
                        price_obj = price_value if isinstance(price_value, dict) else {"price": price_value}
                        price = to_american(price_obj.get("price"))
                        if price is None:
                            continue
                        affiliate_key = str(affiliate_id)
                        book = str(price_obj.get("affiliate_name") or _AFFILIATE_NAMES.get(affiliate_key, f"affiliate_{affiliate_key}"))
                        rows.append({
                            "league_key": self.cfg.league_key,
                            "season": None,
                            "canonical_game_id": event_id,
                            "game_date": commence[:10] if commence else None,
                            "home_team": home,
                            "away_team": away,
                            "book": book,
                            "market": canonical_market,
                            "name": participant_name,
                            "price": price,
                            "point": point if canonical_market != "h2h" else None,
                            "commence_time": commence,
                            "snapshot_horizon": "latest",
                            "is_closing": False,
                            "market_last_update": price_obj.get("updated_at") or line.get("updated_at"),
                            "source": self.source_name,
                            "retrieved_at": retrieved,
                        })
        return rows

    def fetch_schedule(self, date_from: str, date_to: str) -> pd.DataFrame:
        raise SourceUnavailableError("TheRundown is not a schedule source.")

    def fetch_team_game_stats(self, season: int, season_type: str = "Regular Season") -> pd.DataFrame:
        raise SourceUnavailableError("TheRundown is not a team-stats source.")

    def fetch_player_game_stats(self, season: int, season_type: str = "Regular Season") -> pd.DataFrame:
        raise SourceUnavailableError("TheRundown is not a player-stats source.")
