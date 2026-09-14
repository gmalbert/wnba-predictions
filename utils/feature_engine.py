"""Feature engineering for WNBA game prediction.

Every function uses .shift(1) on rolling/expanding calculations to prevent data
leakage — a game's features may only use data available *before* that game.

The pipeline consumes canonical team_game_stats (see utils/data_contracts.py)
rather than source-specific columns, and normalizes rates to per-40 minutes
(WNBA regulation = 40 minutes).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from utils.league_config import get_league_config

_CFG = get_league_config()
NORM_MINUTES = _CFG.normalization_minutes  # 40


def _canonical_id_strings(series: pd.Series) -> pd.Series:
    """Normalize parquet integer/float IDs to stable strings without '.0'."""
    numeric = pd.to_numeric(series, errors="coerce")
    normalized = numeric.round().astype("Int64").astype(str)
    return normalized.where(numeric.notna(), series.astype(str))

# ── Low-level utilities ────────────────────────────────────────────────────────

def compute_rest_days(df: pd.DataFrame, date_col: str = "game_date") -> pd.DataFrame:
    """Add rest_days: calendar days since the team's previous game (cap 14)."""
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values([date_col]).reset_index(drop=True)
    df["rest_days"] = (
        df[date_col].diff().dt.days.fillna(3).clip(lower=1, upper=14).astype(float)
    )
    return df


def compute_back_to_back(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "rest_days" not in df.columns:
        df = compute_rest_days(df)
    df["is_b2b"] = (df["rest_days"] == 1).astype(int)
    df["is_3in4"] = (df["is_b2b"].rolling(3, min_periods=2).sum() >= 2).astype(int)
    return df


def compute_streak(df: pd.DataFrame) -> pd.DataFrame:
    """Add streak: +N wins / -N losses *entering* each game."""
    df = df.copy()
    df = df.sort_values("game_date").reset_index(drop=True)
    streaks: list[int] = []
    current = 0
    for win in df["win"]:
        streaks.append(current)
        current = current + 1 if win == 1 else current - 1
    df["streak"] = streaks
    return df


def add_rolling_features(df: pd.DataFrame, stat_cols: list[str], windows: list[int] | None = None) -> pd.DataFrame:
    """Shifted rolling mean/std for each stat and window (pre-game values)."""
    windows = windows or [3, 5, 10]
    df = df.copy().sort_values("game_date").reset_index(drop=True)
    new_cols: dict[str, pd.Series] = {}
    for col in stat_cols:
        if col not in df.columns:
            continue
        for w in windows:
            min_p = max(1, w // 2)
            new_cols[f"{col}_L{w}"] = df[col].rolling(w, min_periods=min_p).mean().shift(1)
            new_cols[f"{col}_STD{w}"] = df[col].rolling(w, min_periods=min_p).std().shift(1)
    if new_cols:
        df = pd.concat([df, pd.DataFrame(new_cols)], axis=1)
    return df


def add_season_averages(df: pd.DataFrame, stat_cols: list[str]) -> pd.DataFrame:
    """Season-to-date expanding means (shifted 1)."""
    df = df.copy().sort_values("game_date").reset_index(drop=True)
    for col in stat_cols:
        if col not in df.columns:
            continue
        df[f"{col}_SEASON_AVG"] = df[col].expanding(min_periods=1).mean().shift(1)
    return df


def compute_win_pct(df: pd.DataFrame, windows: list[int] | None = None) -> pd.DataFrame:
    windows = windows or [5, 10]
    df = df.copy().sort_values("game_date").reset_index(drop=True)
    df["win_pct_season"] = df["win"].expanding(min_periods=1).mean().shift(1)
    for w in windows:
        df[f"win_pct_L{w}"] = df["win"].rolling(w, min_periods=1).mean().shift(1)
    return df


# ── Derived rates ──────────────────────────────────────────────────────────────

def add_derived_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-game efficiency and per-40-normalized rate stats."""
    df = df.copy()

    # Effective FG% (WNBA 3pt = 3 points)
    if {"field_goals_made", "field_goals_attempted", "three_points_made"}.issubset(df.columns):
        fga = df["field_goals_attempted"].replace(0, np.nan)
        df["efg_pct"] = ((df["field_goals_made"] + 0.5 * df["three_points_made"]) / fga).fillna(0)

    # True shooting %
    if {"points", "field_goals_attempted", "free_throws_attempted"}.issubset(df.columns):
        denom = 2 * (df["field_goals_attempted"] + 0.44 * df["free_throws_attempted"])
        df["ts_pct"] = (df["points"] / denom.replace(0, np.nan)).fillna(0)

    # Turnover rate
    if {"turnovers", "field_goals_attempted", "free_throws_attempted"}.issubset(df.columns):
        denom = df["field_goals_attempted"] + 0.44 * df["free_throws_attempted"] + df["turnovers"]
        df["tov_pct"] = (df["turnovers"] / denom.replace(0, np.nan)).fillna(0)

    # Offensive rebound rate (approximation: OREB / (OREB + opp DREB))
    if {"offensive_rebounds", "defensive_rebounds"}.issubset(df.columns):
        tot = df["offensive_rebounds"] + df["defensive_rebounds"]
        df["oreb_rate"] = (df["offensive_rebounds"] / tot.replace(0, np.nan)).fillna(0)

    # Possession/shot-quality proxies remain useful when tracking feeds are not
    # available.  If a source provides measured possessions, preserve them.
    needed = {"field_goals_attempted", "free_throws_attempted", "offensive_rebounds", "turnovers"}
    if needed.issubset(df.columns):
        estimated = (
            df["field_goals_attempted"]
            + 0.44 * df["free_throws_attempted"]
            - df["offensive_rebounds"]
            + df["turnovers"]
        )
        if "possessions" not in df.columns:
            df["possessions"] = estimated
        else:
            df["possessions"] = pd.to_numeric(df["possessions"], errors="coerce").fillna(estimated)
        poss = df["possessions"].replace(0, np.nan)
        df["offensive_rating"] = (100.0 * df["points"] / poss).replace([np.inf, -np.inf], np.nan)

    if {"three_points_attempted", "field_goals_attempted"}.issubset(df.columns):
        df["three_attempt_rate"] = (
            df["three_points_attempted"] / df["field_goals_attempted"].replace(0, np.nan)
        ).fillna(0)
    if {"free_throws_attempted", "field_goals_attempted"}.issubset(df.columns):
        df["free_throw_rate"] = (
            df["free_throws_attempted"] / df["field_goals_attempted"].replace(0, np.nan)
        ).fillna(0)
    if {"assists", "field_goals_made"}.issubset(df.columns):
        df["assist_rate"] = (df["assists"] / df["field_goals_made"].replace(0, np.nan)).fillna(0)

    # Per-40 normalization (WNBA regulation is 40 minutes, not NBA's 48)
    if "minutes" in df.columns:
        mins = pd.to_numeric(df["minutes"], errors="coerce").clip(lower=1)
        for col in ["points", "rebounds", "assists", "steals", "blocks", "turnovers"]:
            if col in df.columns:
                df[f"{col}_per40"] = (df[col] / mins * NORM_MINUTES).fillna(0)

    return df


# ── Team feature pipeline ──────────────────────────────────────────────────────

TEAM_STAT_COLS = [
    "points", "field_goals_attempted", "efg_pct", "three_points_made",
    "three_points_attempted", "free_throws_made", "free_throws_attempted",
    "offensive_rebounds", "defensive_rebounds", "assists", "turnovers",
    "steals", "blocks", "personal_fouls", "ts_pct", "tov_pct", "oreb_rate",
    "possessions", "offensive_rating", "three_attempt_rate", "free_throw_rate", "assist_rate",
    "roster_continuity", "travel_miles", "timezone_shift_hours", "games_last_4_days",
]


def engineer_team_features(df: pd.DataFrame) -> pd.DataFrame:
    """Full team feature pipeline on one team's canonical game stats."""
    df = df.copy()
    df["game_date"] = pd.to_datetime(df["game_date"])
    df = df.sort_values("game_date").reset_index(drop=True)

    df = compute_rest_days(df)
    df = compute_back_to_back(df)
    df = compute_streak(df)
    df = compute_win_pct(df, windows=[5, 10])
    df = add_derived_rates(df)
    df = add_rolling_features(df, TEAM_STAT_COLS, windows=[3, 5, 10])
    df = add_season_averages(
        df,
        ["points", "points_per40", "turnovers", "assists", "efg_pct", "possessions", "offensive_rating"],
    )

    # Schedule compression: games in last 7 days
    if "game_date" in df.columns:
        df["games_last7"] = (
            df["game_date"]
            .apply(lambda d: df.loc[df["game_date"].between(d - pd.Timedelta(days=7), d - pd.Timedelta(days=1)), "game_date"].count())
        )

    return df


# ── Game-level feature vector ─────────────────────────────────────────────────

def build_game_feature_vector(home_row: pd.Series, away_row: pd.Series) -> pd.Series:
    """Combine pre-game team feature rows into a single game feature vector."""
    d: dict = {}
    for col in home_row.index:
        d[f"home_{col}"] = home_row[col]
    for col in away_row.index:
        d[f"away_{col}"] = away_row[col]

    # Key differentials (home − away)
    d["win_pct_diff"] = d.get("home_win_pct_season", 0) - d.get("away_win_pct_season", 0)
    d["pts_diff_L10"] = d.get("home_points_L10", 0) - d.get("away_points_L10", 0)
    d["rest_diff"] = d.get("home_rest_days", 2) - d.get("away_rest_days", 2)
    d["streak_diff"] = d.get("home_streak", 0) - d.get("away_streak", 0)
    d["efg_diff_L10"] = d.get("home_efg_pct_L10", 0) - d.get("away_efg_pct_L10", 0)
    d["tov_diff_L10"] = d.get("home_tov_pct_L10", 0) - d.get("away_tov_pct_L10", 0)
    d["oreb_diff_L10"] = d.get("home_oreb_rate_L10", 0) - d.get("away_oreb_rate_L10", 0)
    d["pace_diff_L10"] = (
        d.get("home_possessions_L10", d.get("home_field_goals_attempted_L10", 0))
        - d.get("away_possessions_L10", d.get("away_field_goals_attempted_L10", 0))
    )
    d["off_rating_diff_L10"] = d.get("home_offensive_rating_L10", 0) - d.get("away_offensive_rating_L10", 0)
    d["three_rate_diff_L10"] = d.get("home_three_attempt_rate_L10", 0) - d.get("away_three_attempt_rate_L10", 0)
    d["travel_diff"] = d.get("home_travel_miles", 0) - d.get("away_travel_miles", 0)
    d["timezone_shift_diff"] = d.get("home_timezone_shift_hours", 0) - d.get("away_timezone_shift_hours", 0)
    d["workload_diff"] = d.get("home_games_last_4_days", 0) - d.get("away_games_last_4_days", 0)
    d["roster_continuity_diff"] = d.get("home_roster_continuity", 0) - d.get("away_roster_continuity", 0)
    d["is_commissioners_cup"] = max(
        int(bool(d.get("home_is_commissioners_cup", False))),
        int(bool(d.get("away_is_commissioners_cup", False))),
    )
    d["is_playoff"] = max(
        int(bool(d.get("home_is_playoff", False))),
        int(bool(d.get("away_is_playoff", False))),
    )
    d["neutral_site"] = max(
        int(bool(d.get("home_neutral_site", False))),
        int(bool(d.get("away_neutral_site", False))),
    )
    d["is_early_start"] = max(
        int(bool(d.get("home_is_early_start", False))),
        int(bool(d.get("away_is_early_start", False))),
    )
    return pd.Series(d)


def _historical_roster_continuity(player_game_df: pd.DataFrame) -> pd.DataFrame:
    """Create pre-game minutes-overlap continuity without future leakage."""
    if player_game_df is None or player_game_df.empty:
        return pd.DataFrame(columns=["canonical_game_id", "canonical_team_id", "roster_continuity"])
    pg = player_game_df.copy()
    pg["game_date"] = pd.to_datetime(pg.get("game_date"), errors="coerce")
    pg["minutes"] = pd.to_numeric(pg.get("minutes"), errors="coerce").fillna(0).clip(lower=0)
    rows: list[dict] = []
    for team_id, team in pg.groupby("canonical_team_id"):
        games = []
        for game_id, game in team.groupby("canonical_game_id"):
            minutes = game.groupby("canonical_player_id")["minutes"].sum()
            games.append((game["game_date"].max(), game_id, minutes))
        games.sort(key=lambda item: (pd.Timestamp.min if pd.isna(item[0]) else item[0], str(item[1])))
        previous: pd.Series | None = None
        for _, game_id, minutes in games:
            continuity = np.nan
            if previous is not None:
                ids = previous.index.union(minutes.index)
                pair = pd.concat([previous.reindex(ids), minutes.reindex(ids)], axis=1).fillna(0)
                denom = max(float(pair.max(axis=1).sum()), 1.0)
                continuity = float(pair.min(axis=1).sum() / denom)
            rows.append({
                "canonical_game_id": str(game_id),
                "canonical_team_id": team_id,
                "roster_continuity": continuity,
            })
            previous = minutes
    return pd.DataFrame(rows)


def build_training_dataset(
    team_game_df: pd.DataFrame,
    context_df: pd.DataFrame | None = None,
    player_game_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Build a model-ready training DataFrame from canonical team game stats.

    One row per game. TARGET = 1 if the home team won.
    Rolling features are shifted — no future information leaks.
    """
    tg = team_game_df.copy()
    tg["game_date"] = pd.to_datetime(tg["game_date"])

    if context_df is not None and not context_df.empty:
        context = context_df.copy()
        context["canonical_game_id"] = context["canonical_game_id"].astype(str)
        context["canonical_team_id"] = _canonical_id_strings(context["canonical_team_id"])
        tg["canonical_game_id"] = tg["canonical_game_id"].astype(str)
        tg["canonical_team_id"] = _canonical_id_strings(tg["canonical_team_id"])
        context_cols = [
            "canonical_game_id", "canonical_team_id", "travel_miles", "timezone_shift_hours",
            "games_last_4_days", "is_cross_country", "is_early_start",
            "is_commissioners_cup", "is_playoff", "neutral_site",
        ]
        tg = tg.merge(context[[c for c in context_cols if c in context.columns]], on=["canonical_game_id", "canonical_team_id"], how="left")
    if player_game_df is not None and not player_game_df.empty:
        continuity = _historical_roster_continuity(player_game_df)
        tg["canonical_game_id"] = tg["canonical_game_id"].astype(str)
        tg["canonical_team_id"] = _canonical_id_strings(tg["canonical_team_id"])
        continuity["canonical_game_id"] = continuity["canonical_game_id"].astype(str)
        continuity["canonical_team_id"] = _canonical_id_strings(continuity["canonical_team_id"])
        tg = tg.merge(continuity, on=["canonical_game_id", "canonical_team_id"], how="left")

    team_features: dict[int, pd.DataFrame] = {}
    for team_id, grp in tg.groupby("canonical_team_id"):
        team_features[int(team_id)] = engineer_team_features(grp.sort_values("game_date").reset_index(drop=True))

    rows = []
    home_games = tg[tg["is_home"] == 1]
    for _, home_row in home_games.iterrows():
        game_id = str(home_row["canonical_game_id"])
        home_tid = int(home_row["canonical_team_id"])
        away_rows = tg[
            (tg["canonical_game_id"] == game_id)
            & (tg["canonical_team_id"].astype(str) != str(home_tid))
        ]
        if away_rows.empty:
            continue
        away_tid = int(away_rows.iloc[0]["canonical_team_id"])

        hf = team_features.get(home_tid)
        af = team_features.get(away_tid)
        if hf is None or af is None:
            continue

        hfrow = hf[hf["canonical_game_id"] == game_id]
        afrow = af[af["canonical_game_id"] == game_id]
        if hfrow.empty or afrow.empty:
            continue

        fv = build_game_feature_vector(hfrow.iloc[0], afrow.iloc[0])
        fv["game_id"] = game_id
        fv["game_date"] = home_row["game_date"]
        fv["home_team_id"] = home_tid
        fv["away_team_id"] = away_tid
        fv["target"] = int(home_row["win"]) if pd.notna(home_row.get("win")) else None
        fv["home_points"] = home_row.get("points", np.nan)
        fv["away_points"] = away_rows.iloc[0].get("points", np.nan)
        fv["margin"] = fv["home_points"] - fv["away_points"]
        fv["total_points"] = fv["home_points"] + fv["away_points"]
        rows.append(fv)

    return pd.DataFrame(rows).reset_index(drop=True)
