"""Typed league configuration loaded from ``config/league.toml``.

All WNBA-specific constants live here so no module hardcodes league values.
Loading is lazy (no side effects on import) and validated at first use.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "league.toml"


@dataclass(frozen=True)
class LeagueConfig:
    """Immutable league configuration."""

    league_key: str
    display_name: str
    stats_league_id: str
    season_format: str
    period_minutes: int
    regulation_periods: int
    timezone: str
    default_season_type: str
    playoff_label: str
    normalization_minutes: int
    current_season: int
    historical_start: int
    _overrides: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def regulation_minutes(self) -> int:
        """Regulation minutes = period_minutes × regulation_periods (40 for WNBA)."""
        return self.period_minutes * self.regulation_periods

    def normalize_season(self, value: int | str) -> str:
        """Return a canonical calendar-year season string, rejecting split-year input."""
        s = str(value).strip()
        if "-" in s:
            raise ValueError(
                f"Split-year season '{s}' is invalid for {self.display_name} "
                "(seasons are calendar years)."
            )
        return s

    def storage_namespace(self, *parts: str) -> Path:
        """League-scoped storage path under data_files/."""
        root = Path(__file__).resolve().parent.parent / "data_files"
        return root.joinpath(self.league_key, *parts)


@lru_cache(maxsize=1)
def load_league_config(path: Path | None = None) -> LeagueConfig:
    """Load and validate league.toml. Results are cached for the process."""
    p = Path(path) if path else _CONFIG_PATH
    with p.open("rb") as f:
        raw = tomllib.load(f)

    required = {
        "league_key",
        "display_name",
        "stats_league_id",
        "season_format",
        "period_minutes",
        "regulation_periods",
        "timezone",
        "default_season_type",
        "playoff_label",
        "normalization_minutes",
        "current_season",
        "historical_start",
    }
    missing = required - set(raw)
    if missing:
        raise ValueError(f"league.toml missing required keys: {sorted(missing)}")

    if raw["league_key"] != "wnba":
        raise ValueError(
            f"Expected league_key='wnba' but found '{raw['league_key']}'. "
            "This application is WNBA-only and rejects other league configs."
        )

    cfg = LeagueConfig(**{k: raw[k] for k in required}, _overrides=raw.get("season_overrides", {}))
    if cfg.regulation_minutes != cfg.normalization_minutes:
        raise ValueError(
            f"normalization_minutes ({cfg.normalization_minutes}) must equal "
            f"regulation_minutes ({cfg.regulation_minutes}) for {cfg.display_name}."
        )
    return cfg


# Module-level convenience accessor. Importing this module performs no I/O;
# the config is only parsed when ``get_league_config()`` is first called.
@lru_cache(maxsize=1)
def get_league_config() -> LeagueConfig:
    return load_league_config()


LEAGUE_CONFIG: LeagueConfig = None  # type: ignore[assignment]  # set by ensure_league_config()


def ensure_league_config() -> LeagueConfig:
    """Load the config once and stash it on the module for direct attribute access."""
    global LEAGUE_CONFIG
    if LEAGUE_CONFIG is None:
        LEAGUE_CONFIG = get_league_config()
    return LEAGUE_CONFIG
