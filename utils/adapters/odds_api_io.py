"""Odds-API.io adapter for WNBA game markets."""

from __future__ import annotations

import datetime as dt
import os
from typing import Any

import pandas as pd
import requests

from utils.adapters.base import SourceUnavailableError
from utils.adapters.odds_common import (
    empty_odds,
    load_env_key,
    now_utc,
    numeric_point,
    to_american,
)
from utils.data_contracts import ODDS_COLUMNS
from utils.league_config import get_league_config

_BASE = "https://api.odds-api.io/v3"
_TIMEOUT = 30
_LOOKAHEAD_DAYS = 14
_DEFAULT_BOOKMAKERS = "DraftKings,Bet365"
_DEFAULT_MAX_REQUESTS = 20


def _items(value: object) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _event_list(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("events"), list):
            return [item for item in payload["events"] if isinstance(item, dict)]
        if isinstance(payload.get("data"), list):
            return [item for item in payload["data"] if isinstance(item, dict)]
        if payload.get("id") is not None:
            return [payload]
        return [item for item in payload.values() if isinstance(item, dict) and item.get("id") is not None]
    return []


def _is_wnba(event: dict) -> bool:
    league = event.get("league") or {}
    sport = event.get("sport") or {}
    text = " ".join(
        str(value).lower()
        for value in (
            league.get("name", ""), league.get("slug", ""),
            sport.get("name", ""), sport.get("slug", ""),
        )
    )
    return "wnba" in text


def _event_time(event: dict) -> str:
    return str(event.get("date") or event.get("commence_time") or "")


class OddsApiIoAdapter:
    """Fetch WNBA events and core odds from Odds-API.io."""

    source_name = "odds_api_io"

    def __init__(self, api_key: str | None = None) -> None:
        self.cfg = get_league_config()
        self.api_key = api_key or load_env_key("ODDS_API_IO_KEY")
        self.bookmakers = os.getenv("ODDS_API_IO_BOOKMAKERS", _DEFAULT_BOOKMAKERS)
        try:
            self.max_requests = max(1, int(os.getenv("ODDS_API_IO_MAX_REQUESTS", str(_DEFAULT_MAX_REQUESTS))))
        except ValueError:
            self.max_requests = _DEFAULT_MAX_REQUESTS
        self._request_count = 0

    def _get(self, path: str, params: dict[str, object]) -> object:
        if not self.api_key:
            raise SourceUnavailableError("ODDS_API_IO_KEY is not set")
        if self._request_count >= self.max_requests:
            raise SourceUnavailableError(
                f"Odds-API.io request budget exhausted ({self.max_requests}); stopped without retrying."
            )
        self._request_count += 1
        try:
            response = requests.get(f"{_BASE}/{path.lstrip('/')}", params=params, timeout=_TIMEOUT)
            if response.status_code == 429:
                raise SourceUnavailableError("Odds-API.io rate limit reached; stopped without retrying.")
            response.raise_for_status()
            return response.json()
        except SourceUnavailableError:
            raise
        except Exception as exc:
            raise SourceUnavailableError(f"Odds-API.io request failed: {exc}") from exc

    def fetch_odds(self) -> pd.DataFrame:
        self._request_count = 0
        now = dt.datetime.now(dt.timezone.utc)
        params: dict[str, object] = {
            "apiKey": self.api_key,
            "sport": "basketball",
            "status": "pending",
            "from": now.isoformat().replace("+00:00", "Z"),
            "to": (now + dt.timedelta(days=_LOOKAHEAD_DAYS)).isoformat().replace("+00:00", "Z"),
            "limit": 5000,
        }
        league = os.getenv("ODDS_API_IO_LEAGUE", "").strip()
        if league:
            params["league"] = league
        events = [event for event in _event_list(self._get("events", params)) if _is_wnba(event)]
        if not events:
            return empty_odds()

        rows: list[dict[str, Any]] = []
        for start in range(0, len(events), 10):
            batch = events[start:start + 10]
            odds_payload = self._get(
                "odds/multi",
                {
                    "apiKey": self.api_key,
                    "eventIds": ",".join(str(event.get("id")) for event in batch),
                    "bookmakers": self.bookmakers,
                },
            )
            for event in _event_list(odds_payload):
                rows.extend(self._normalize_event(event))
        return pd.DataFrame(rows, columns=ODDS_COLUMNS) if rows else empty_odds()

    def _normalize_event(self, event: dict) -> list[dict[str, Any]]:
        event_id = str(event.get("id", ""))
        home = str(event.get("home", event.get("home_team", "")))
        away = str(event.get("away", event.get("away_team", "")))
        commence = _event_time(event)
        retrieved = now_utc()
        rows: list[dict[str, Any]] = []
        bookmakers = event.get("bookmakers") or {}
        if not isinstance(bookmakers, dict):
            return rows

        for bookmaker, market_values in bookmakers.items():
            for market in _items(market_values):
                market_name = str(market.get("name", market.get("key", ""))).lower().replace("_", " ")
                market_last_update = market.get("updatedAt") or market.get("updated_at")
                for line in _items(market.get("odds")):
                    if market_name in {"ml", "moneyline", "money line", "h2h"}:
                        for side, team in (("home", home), ("away", away)):
                            price = to_american(line.get(side))
                            if price is not None and team:
                                rows.append(self._row(event_id, commence, home, away, bookmaker, "h2h", team, price, None, retrieved, market_last_update))
                    elif "spread" in market_name or "handicap" in market_name:
                        point = line.get("hdp", line.get("point", line.get("handicap")))
                        for side, team in (("home", home), ("away", away)):
                            price = to_american(line.get(side))
                            if price is not None and team:
                                rows.append(self._row(event_id, commence, home, away, bookmaker, "spreads", team, price, numeric_point(point), retrieved, market_last_update))
                    elif "total" in market_name or "over/under" in market_name:
                        point = line.get("points", line.get("point", line.get("total", line.get("max"))))
                        for side in ("over", "under"):
                            price = to_american(line.get(side))
                            if price is not None:
                                rows.append(self._row(event_id, commence, home, away, bookmaker, "totals", side.title(), price, numeric_point(point), retrieved, market_last_update))
        return rows

    def _row(self, event_id: str, commence: str, home: str, away: str, bookmaker: object, market: str, name: str, price: int, point: float | None, retrieved: str, market_last_update: object = None) -> dict[str, Any]:
        return {
            "league_key": self.cfg.league_key,
            "season": None,
            "canonical_game_id": event_id,
            "game_date": commence[:10] if commence else None,
            "home_team": home,
            "away_team": away,
            "book": str(bookmaker),
            "market": market,
            "name": name,
            "price": price,
            "point": point,
            "commence_time": commence,
            "snapshot_horizon": "latest",
            "is_closing": False,
            "market_last_update": market_last_update,
            "source": self.source_name,
            "retrieved_at": retrieved,
        }

    def fetch_schedule(self, date_from: str, date_to: str) -> pd.DataFrame:
        raise SourceUnavailableError("Odds-API.io is not a schedule source.")

    def fetch_team_game_stats(self, season: int, season_type: str = "Regular Season") -> pd.DataFrame:
        raise SourceUnavailableError("Odds-API.io is not a team-stats source.")

    def fetch_player_game_stats(self, season: int, season_type: str = "Regular Season") -> pd.DataFrame:
        raise SourceUnavailableError("Odds-API.io is not a player-stats source.")
