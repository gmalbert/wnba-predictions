"""Source capability and priority registry.

Defines which source is the primary/fallback for each data type and exposes
helpers the data_fetcher façade uses to pick adapters and record health.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Primary → fallback order per data type.
SOURCE_PRIORITY: dict[str, list[str]] = {
    "schedule": ["wnba_stats", "espn", "balldontlie"],
    "team_game_stats": ["wehoop", "espn", "wnba_stats", "balldontlie"],
    "player_game_stats": ["wehoop", "wnba_stats", "espn", "balldontlie"],
    "standings": ["wnba_stats", "espn", "balldontlie"],
    "rosters": ["espn", "wnba_stats", "balldontlie"],
    "injuries": ["espn", "wnba_stats"],
    "odds": ["the_odds_api", "espn"],
    "officials": ["wehoop", "espn"],
    "play_by_play": ["wehoop", "espn"],
}

ALL_SOURCES = sorted({s for srcs in SOURCE_PRIORITY.values() for s in srcs})


@dataclass
class SourceHealth:
    """Per-source freshness/capability record used by the Data Health page."""

    source: str
    data_type: str
    last_success: str | None = None
    last_attempt: str | None = None
    ok: bool = False
    error: str | None = None
    records: int = 0
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "data_type": self.data_type,
            "last_success": self.last_success,
            "last_attempt": self.last_attempt,
            "ok": self.ok,
            "error": self.error,
            "records": self.records,
            **self.extra,
        }


def source_supports(source: str, data_type: str) -> bool:
    """True if a source claims capability for a data type."""
    return source in SOURCE_PRIORITY.get(data_type, [])


def priority_for(data_type: str) -> list[str]:
    """Ordered list of sources to try for a data type."""
    return SOURCE_PRIORITY.get(data_type, [])
