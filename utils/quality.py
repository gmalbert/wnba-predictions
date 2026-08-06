"""Data quality: validation, freshness, and completeness checks.

Used by scripts/validate_data.py and surfaced on the Data Health page.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class QualityIssue:
    """A single data-quality finding."""

    check: str
    severity: str  # error | warning | info
    message: str
    count: int = 0

    def to_dict(self) -> dict:
        return {"check": self.check, "severity": self.severity, "message": self.message, "count": self.count}


def _as_datetime(v):
    try:
        return pd.to_datetime(v)
    except Exception:
        return None


def check_games(games: pd.DataFrame) -> list[QualityIssue]:
    """Validate the canonical games table."""
    issues: list[QualityIssue] = []
    if games is None or games.empty:
        return [QualityIssue("games", "warning", "No games data present")]
    if "canonical_game_id" not in games.columns:
        return [QualityIssue("games", "error", "games missing canonical_game_id")]

    dupes = int(games.duplicated("canonical_game_id").sum())
    if dupes:
        issues.append(QualityIssue("games", "error", f"Duplicate canonical_game_id rows", dupes))

    missing_home = int(games["home_team_id"].isna().sum())
    missing_away = int(games["away_team_id"].isna().sum())
    if missing_home:
        issues.append(QualityIssue("games", "warning", "Missing home_team_id", missing_home))
    if missing_away:
        issues.append(QualityIssue("games", "warning", "Missing away_team_id", missing_away))

    no_date = int(games["game_date"].isna().sum())
    if no_date:
        issues.append(QualityIssue("games", "warning", "Missing game_date", no_date))
    return issues


def check_team_games(tg: pd.DataFrame) -> list[QualityIssue]:
    """Validate canonical team game stats (two rows per completed game)."""
    issues: list[QualityIssue] = []
    if tg is None or tg.empty:
        return [QualityIssue("team_game_stats", "warning", "No team game stats present")]
    if "canonical_game_id" not in tg.columns or "canonical_team_id" not in tg.columns:
        return [QualityIssue("team_game_stats", "error", "team_game_stats missing key columns")]

    completed = tg[tg.get("win", pd.Series(dtype=bool)).notna()] if "win" in tg.columns else tg
    counts = completed.groupby("canonical_game_id")["canonical_team_id"].nunique()
    bad = int((counts != 2).sum())
    if bad:
        issues.append(QualityIssue(
            "team_game_stats", "error",
            f"Games without exactly two team rows", bad,
        ))

    dupes = int(tg.duplicated(["canonical_game_id", "canonical_team_id"]).sum())
    if dupes:
        issues.append(QualityIssue("team_game_stats", "error", "Duplicate team rows", dupes))
    return issues


def check_player_games(pg: pd.DataFrame) -> list[QualityIssue]:
    """Validate canonical player game stats."""
    issues: list[QualityIssue] = []
    if pg is None or pg.empty:
        return [QualityIssue("player_game_stats", "warning", "No player game stats present")]
    if "canonical_player_id" not in pg.columns:
        return [QualityIssue("player_game_stats", "error", "player_game_stats missing player id")]

    missing_team = int(pg["canonical_team_id"].isna().sum())
    if missing_team:
        issues.append(QualityIssue("player_game_stats", "warning", "Player rows missing team", missing_team))

    # Implausible minutes (> 60 for a 40-minute regulation game + OT)
    if "minutes" in pg.columns:
        mins = pd.to_numeric(pg["minutes"], errors="coerce")
        implausible = int((mins > 60).sum())
        if implausible:
            issues.append(QualityIssue("player_game_stats", "warning", "Implausible minutes (>60)", implausible))
    return issues


def check_injuries(inj: pd.DataFrame) -> list[QualityIssue]:
    """Validate injuries table."""
    issues: list[QualityIssue] = []
    if inj is None or inj.empty:
        return [QualityIssue("injuries", "info", "No injury data (may be off-season)")]
    missing_status = int(inj["status"].isna().sum()) if "status" in inj.columns else 0
    if missing_status:
        issues.append(QualityIssue("injuries", "warning", "Injuries missing status", missing_status))
    return issues


def check_odds(odds: pd.DataFrame) -> list[QualityIssue]:
    """Validate odds snapshots."""
    issues: list[QualityIssue] = []
    if odds is None or odds.empty:
        return [QualityIssue("odds", "info", "No odds snapshots present")]
    return issues


def check_freshness(datasets: dict[str, pd.DataFrame], max_age_hours: dict[str, float]) -> list[QualityIssue]:
    """Report freshness for each dataset keyed by name with a max-age threshold."""
    issues: list[QualityIssue] = []
    now = dt.datetime.now(dt.timezone.utc)
    for name, df in datasets.items():
        if df is None or df.empty:
            issues.append(QualityIssue("freshness", "warning", f"{name}: no data"))
            continue
        if "retrieved_at" not in df.columns:
            continue
        ts = pd.to_datetime(df["retrieved_at"], errors="coerce", utc=True)
        if ts.isna().all():
            continue
        newest = ts.max()
        age_h = (now - newest).total_seconds() / 3600.0
        threshold = max_age_hours.get(name, 24.0)
        if age_h > threshold:
            issues.append(QualityIssue(
                "freshness", "warning",
                f"{name}: newest row {age_h:.1f}h old (threshold {threshold:.0f}h)",
            ))
    return issues


def summarize(issues: list[QualityIssue]) -> dict:
    """Summarize issues into a compact report dict."""
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    return {
        "error_count": len(errors),
        "warning_count": len(warnings),
        "healthy": len(errors) == 0,
        "issues": [i.to_dict() for i in issues],
    }
