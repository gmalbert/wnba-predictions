"""Base adapter protocol shared by all WNBA source adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class BasketballDataAdapter(Protocol):
    """Common interface every source adapter implements.

    Each method returns a DataFrame normalized to the canonical schema in
    utils.data_contracts.py. Adapters raise SourceUnavailableError when the
    source cannot be reached so the orchestrator can fall back.
    """

    source_name: str

    def fetch_schedule(self, date_from: str, date_to: str) -> pd.DataFrame: ...

    def fetch_team_game_stats(self, season: int, season_type: str = "Regular Season") -> pd.DataFrame: ...

    def fetch_player_game_stats(self, season: int, season_type: str = "Regular Season") -> pd.DataFrame: ...

    def fetch_standings(self, season: int) -> pd.DataFrame: ...

    def fetch_rosters(self, season: int) -> pd.DataFrame: ...

    def fetch_injuries(self, as_of: str | None = None) -> pd.DataFrame: ...


class SourceUnavailableError(Exception):
    """Raised when a source cannot be reached or returns unusable data."""


class SchemaMismatchError(Exception):
    """Raised when a source response no longer matches its contract."""


class DataIncompleteError(Exception):
    """Raised when a source returns data but important pieces are missing."""


class IdentityMappingError(Exception):
    """Raised when source IDs cannot be mapped to canonical IDs."""
