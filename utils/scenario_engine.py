"""WNBA availability, minutes, lineup, travel, and scenario uncertainty.

The functions in this module are deliberately source-agnostic.  They operate
on canonical frames and always accept an ``as_of`` timestamp so replay jobs do
not accidentally use a later injury report, starter confirmation, or workload
observation.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from dataclasses import dataclass
from itertools import product
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


STATUS_PROBABILITY = {
    "available": 0.99,
    "active": 0.99,
    "probable": 0.85,
    "questionable": 0.50,
    "game time decision": 0.50,
    "day-to-day": 0.60,
    "doubtful": 0.15,
    "out": 0.01,
    "inactive": 0.01,
    "suspended": 0.01,
}


def _utc_timestamp(value: object | None = None) -> pd.Timestamp:
    if value is None:
        return pd.Timestamp.now(tz="UTC")
    stamp = pd.to_datetime(value, errors="coerce", utc=True)
    return stamp if pd.notna(stamp) else pd.Timestamp.now(tz="UTC")


def status_probability(status: object) -> float:
    """Map a news status to a conservative probability of playing."""
    text = str(status or "available").strip().lower()
    for key, value in STATUS_PROBABILITY.items():
        if key in text:
            return value
    return 0.75 if text and text != "nan" else 0.95


def classify_role(minutes_mean: float) -> str:
    if minutes_mean >= 29:
        return "star"
    if minutes_mean >= 22:
        return "starter"
    if minutes_mean >= 12:
        return "rotation"
    return "reserve"


def mixture_prediction(
    scenarios: Sequence[tuple[float, float, float]],
) -> tuple[float, float]:
    """Collapse weighted Normal scenarios into a mean and standard deviation.

    Each tuple is ``(probability, mean, standard_deviation)``.  We normalize
    weights to make editor-created scenarios safe even when rounding means the
    submitted probabilities do not add to exactly one.
    """
    if not scenarios:
        return 0.0, 0.0
    weights = np.asarray([max(float(w), 0.0) for w, _, _ in scenarios], dtype=float)
    total = float(weights.sum())
    if total <= 0:
        weights = np.repeat(1.0 / len(scenarios), len(scenarios))
    else:
        weights /= total
    means = np.asarray([float(m) for _, m, _ in scenarios], dtype=float)
    sds = np.asarray([max(float(s), 0.0) for _, _, s in scenarios], dtype=float)
    mean = float(np.sum(weights * means))
    second = float(np.sum(weights * (sds * sds + means * means)))
    return mean, math.sqrt(max(second - mean * mean, 0.0))


def _as_of_filter(df: pd.DataFrame, as_of: object | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()
    result = df.copy()
    cutoff = _utc_timestamp(as_of)
    for col in ("observed_at", "retrieved_at"):
        if col in result.columns:
            observed = pd.to_datetime(result[col], errors="coerce", utc=True)
            result = result[observed.isna() | (observed <= cutoff)]
            break
    return result


def estimate_minutes_distributions(
    player_games: pd.DataFrame,
    availability: pd.DataFrame | None = None,
    *,
    as_of: object | None = None,
    recent_games: int = 10,
    prior_games: float = 5.0,
) -> pd.DataFrame:
    """Estimate player minutes with role-aware empirical-Bayes partial pooling.

    Recent player means are shrunk toward the team rotation mean.  Variances
    are also pooled so rookies, returners, and expansion-team cold starts do
    not receive implausibly certain projections from one or two appearances.
    """
    columns = [
        "canonical_player_id", "canonical_team_id", "player_name", "games",
        "minutes_mean_if_active", "minutes_sd_if_active", "availability_probability",
        "minutes_mean", "minutes_sd", "role", "status", "confirmed_starter",
        "status_detail", "impact_per_minute", "observed_at",
    ]
    if player_games is None or player_games.empty:
        return pd.DataFrame(columns=columns)

    pg = player_games.copy()
    if "game_date" in pg.columns:
        dates = pd.to_datetime(pg["game_date"], errors="coerce", utc=True)
        pg = pg[dates.isna() | (dates <= _utc_timestamp(as_of))]
        pg = pg.assign(_game_date=dates).sort_values("_game_date")
    pg["minutes"] = pd.to_numeric(pg.get("minutes"), errors="coerce").clip(lower=0, upper=60)
    pg = pg.dropna(subset=["canonical_player_id", "canonical_team_id", "minutes"])
    if pg.empty:
        return pd.DataFrame(columns=columns)

    availability = _as_of_filter(availability, as_of)
    try:
        from utils.identity import load_players

        player_reference = load_players()
        player_names = {
            str(row.get("canonical_player_id")): str(row.get("display_name", ""))
            for row in player_reference.to_dict("records")
            if pd.notna(row.get("canonical_player_id"))
        }
    except Exception:
        player_names = {}
    latest_availability: dict[str, pd.Series] = {}
    if availability is not None and not availability.empty and "canonical_player_id" in availability.columns:
        order_col = "observed_at" if "observed_at" in availability.columns else "retrieved_at"
        if order_col in availability.columns:
            availability = availability.assign(
                _observed=pd.to_datetime(availability[order_col], errors="coerce", utc=True)
            ).sort_values("_observed")
        for pid, group in availability.dropna(subset=["canonical_player_id"]).groupby("canonical_player_id"):
            latest_availability[str(pid)] = group.iloc[-1]

    team_priors = pg.groupby("canonical_team_id")["minutes"].agg(["mean", "std"])
    league_mean = float(pg["minutes"].mean())
    league_sd = float(pg["minutes"].std(ddof=0)) if len(pg) > 1 else 8.0
    rows: list[dict] = []
    for (pid, tid), group in pg.groupby(["canonical_player_id", "canonical_team_id"]):
        recent = group.tail(recent_games)
        n = float(len(recent))
        raw_mean = float(recent["minutes"].mean())
        raw_sd = float(recent["minutes"].std(ddof=0)) if len(recent) > 1 else league_sd
        team_prior = team_priors.loc[tid]
        prior_mean = float(team_prior.get("mean", league_mean))
        prior_sd = float(team_prior.get("std", league_sd))
        if not np.isfinite(prior_sd) or prior_sd <= 0:
            prior_sd = league_sd
        shrink = n / (n + prior_games)
        active_mean = shrink * raw_mean + (1.0 - shrink) * prior_mean
        active_var = shrink * raw_sd**2 + (1.0 - shrink) * prior_sd**2
        active_sd = max(math.sqrt(max(active_var, 0.0)), 2.0)

        obs = latest_availability.get(str(pid))
        status = str(obs.get("status", "Available")) if obs is not None else "Available"
        status_detail = str(obs.get("status_detail", "")) if obs is not None else ""
        play_prob = (
            float(obs.get("availability_probability"))
            if obs is not None and pd.notna(obs.get("availability_probability"))
            else status_probability(status)
        )
        confirmed = bool(obs.get("confirmed_starter", False)) if obs is not None else False
        if confirmed:
            play_prob = max(play_prob, 0.99)

        # Mixture of active minutes and zero minutes.
        minutes_mean = play_prob * active_mean
        second = play_prob * (active_sd**2 + active_mean**2)
        minutes_sd = math.sqrt(max(second - minutes_mean**2, 0.0))

        points = pd.to_numeric(recent.get("points"), errors="coerce") if "points" in recent else pd.Series(dtype=float)
        assists = pd.to_numeric(recent.get("assists"), errors="coerce") if "assists" in recent else pd.Series(dtype=float)
        rebounds = pd.to_numeric(recent.get("rebounds"), errors="coerce") if "rebounds" in recent else pd.Series(dtype=float)
        production = float((points.fillna(0) + 0.7 * assists.fillna(0) + 0.35 * rebounds.fillna(0)).mean()) if len(recent) else 0.0
        raw_impact = production / max(raw_mean, 1.0) / 10.0
        impact = shrink * raw_impact + (1.0 - shrink) * 0.04

        player_name = ""
        if "player_name" in group.columns and group["player_name"].notna().any():
            player_name = str(group.loc[group["player_name"].notna(), "player_name"].iloc[-1])
        elif obs is not None:
            player_name = str(obs.get("player_name", ""))
        if not player_name:
            player_name = player_names.get(str(pid), "")

        rows.append({
            "canonical_player_id": pid,
            "canonical_team_id": tid,
            "player_name": player_name,
            "games": int(n),
            "minutes_mean_if_active": round(active_mean, 2),
            "minutes_sd_if_active": round(active_sd, 2),
            "availability_probability": round(float(np.clip(play_prob, 0.0, 1.0)), 3),
            "minutes_mean": round(minutes_mean, 2),
            "minutes_sd": round(minutes_sd, 2),
            "role": classify_role(active_mean),
            "status": status,
            "confirmed_starter": confirmed,
            "status_detail": status_detail,
            "impact_per_minute": round(float(np.clip(impact, -0.25, 0.25)), 4),
            "observed_at": _utc_timestamp(as_of).isoformat(),
        })
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["canonical_team_id", "minutes_mean_if_active"], ascending=[True, False]
    ).reset_index(drop=True)


def condition_rotation_for_game(
    rotation: pd.DataFrame,
    home_team_id: int,
    away_team_id: int,
    home_context: pd.Series | dict,
    away_context: pd.Series | dict,
    *,
    expected_margin: float = 0.0,
) -> pd.DataFrame:
    """Condition minutes on rest, workload, role, score context, and return state."""
    if rotation is None or rotation.empty:
        return pd.DataFrame() if rotation is None else rotation.copy()
    result = rotation.copy()
    for team_id, context in ((home_team_id, home_context), (away_team_id, away_context)):
        mask = result["canonical_team_id"].astype(str) == str(team_id)
        if not mask.any():
            continue
        multiplier = 1.0
        rest_days = float(context.get("rest_days", 3) or 3)
        games_last4 = float(context.get("games_last_4_days", 0) or 0)
        if rest_days <= 1:
            multiplier *= 0.97
            result.loc[mask, "minutes_sd_if_active"] *= 1.08
        if games_last4 >= 2:
            multiplier *= 0.96
            result.loc[mask, "minutes_sd_if_active"] *= 1.06
        result.loc[mask, "minutes_mean_if_active"] *= multiplier

        # Large expected margins widen rotation uncertainty: high-minute roles
        # lose a little mean while reserves gain it. This is a distributional
        # score-context adjustment, never an assumed motivation effect.
        if abs(float(expected_margin)) >= 12:
            starters = mask & result["role"].isin(["star", "starter"])
            reserves = mask & result["role"].isin(["reserve", "rotation"])
            result.loc[starters, "minutes_mean_if_active"] *= 0.96
            result.loc[reserves, "minutes_mean_if_active"] *= 1.05
            result.loc[mask, "minutes_sd_if_active"] *= 1.10

        return_text = (
            result.loc[mask, "status"].fillna("").astype(str)
            + " "
            + result.loc[mask, "status_detail"].fillna("").astype(str)
        ).str.lower()
        returning = return_text.str.contains("return|restriction|ramp|conditioning", regex=True)
        returning_index = return_text.index[returning]
        result.loc[returning_index, "minutes_mean_if_active"] *= 0.90
        result.loc[returning_index, "minutes_sd_if_active"] *= 1.25

    play_probability = pd.to_numeric(result["availability_probability"], errors="coerce").fillna(0.95)
    active_mean = pd.to_numeric(result["minutes_mean_if_active"], errors="coerce").fillna(0)
    active_sd = pd.to_numeric(result["minutes_sd_if_active"], errors="coerce").fillna(6)
    result["minutes_mean"] = play_probability * active_mean
    second = play_probability * (active_sd**2 + active_mean**2)
    result["minutes_sd"] = np.sqrt(np.maximum(second - result["minutes_mean"] ** 2, 0.0))
    return result


def roster_continuity(player_games: pd.DataFrame, team_id: int, *, as_of: object | None = None) -> float:
    """Minutes-weighted overlap between a team's two most recent rotations."""
    if player_games is None or player_games.empty or "canonical_game_id" not in player_games.columns:
        return float("nan")
    pg = player_games[player_games["canonical_team_id"].astype(str) == str(team_id)].copy()
    if pg.empty:
        return float("nan")
    if "game_date" in pg.columns:
        pg["_date"] = pd.to_datetime(pg["game_date"], errors="coerce", utc=True)
        pg = pg[pg["_date"].isna() | (pg["_date"] <= _utc_timestamp(as_of))]
    game_order = (
        pg.groupby("canonical_game_id")["_date"].max().sort_values().index.tolist()
        if "_date" in pg.columns
        else pg["canonical_game_id"].drop_duplicates().tolist()
    )
    if len(game_order) < 2:
        return float("nan")
    a = pg[pg["canonical_game_id"] == game_order[-2]].set_index("canonical_player_id")["minutes"]
    b = pg[pg["canonical_game_id"] == game_order[-1]].set_index("canonical_player_id")["minutes"]
    a = pd.to_numeric(a, errors="coerce").fillna(0).clip(lower=0)
    b = pd.to_numeric(b, errors="coerce").fillna(0).clip(lower=0)
    ids = a.index.union(b.index)
    denom = max(float(pd.concat([a, b], axis=1).fillna(0).max(axis=1).sum()), 1.0)
    overlap = float(pd.concat([a.reindex(ids), b.reindex(ids)], axis=1).fillna(0).min(axis=1).sum())
    return round(float(np.clip(overlap / denom, 0.0, 1.0)), 3)


def inferred_lineup_matchup(
    rotation: pd.DataFrame,
    home_team_id: int,
    away_team_id: int,
) -> list[dict]:
    """Return the likely top-five rotations for a lightweight matchup view."""
    if rotation is None or rotation.empty:
        return []
    rows: list[dict] = []
    for side, tid in (("home", home_team_id), ("away", away_team_id)):
        team = rotation[rotation["canonical_team_id"].astype(str) == str(tid)].nlargest(
            5, "minutes_mean"
        )
        for rank, (_, player) in enumerate(team.iterrows(), start=1):
            rows.append({
                "side": side,
                "rank": rank,
                "player_id": str(player.get("canonical_player_id", "")),
                "player": player.get("player_name") or f"Player {player.get('canonical_player_id', '')}",
                "minutes_mean": round(float(player.get("minutes_mean", 0.0)), 1),
                "minutes_sd": round(float(player.get("minutes_sd", 0.0)), 1),
                "role": player.get("role", "rotation"),
                "status": player.get("status", "Available"),
            })
    return rows


def build_margin_scenarios(
    base_margin: float,
    base_sd: float,
    rotation: pd.DataFrame,
    home_team_id: int,
    away_team_id: int,
    *,
    max_uncertain_players: int = 4,
) -> list[tuple[float, float, float]]:
    """Enumerate the highest-leverage availability branches for a game."""
    if rotation is None or rotation.empty:
        return [(1.0, float(base_margin), float(base_sd))]
    relevant = rotation[
        rotation["canonical_team_id"].astype(str).isin([str(home_team_id), str(away_team_id)])
    ].copy()
    relevant["uncertainty_score"] = (
        relevant["availability_probability"]
        * (1 - relevant["availability_probability"])
        * relevant["minutes_mean_if_active"]
        * relevant["impact_per_minute"].abs()
    )
    uncertain = relevant[
        relevant["availability_probability"].between(0.05, 0.95, inclusive="both")
    ].nlargest(max_uncertain_players, "uncertainty_score")
    if uncertain.empty:
        return [(1.0, float(base_margin), float(base_sd))]

    scenarios: list[tuple[float, float, float]] = []
    for states in product([0, 1], repeat=len(uncertain)):
        weight = 1.0
        margin = float(base_margin)
        for state, (_, player) in zip(states, uncertain.iterrows()):
            play_prob = float(player["availability_probability"])
            weight *= play_prob if state else 1.0 - play_prob
            if not state:
                impact = float(player["minutes_mean_if_active"]) * float(player["impact_per_minute"])
                if str(player["canonical_team_id"]) == str(home_team_id):
                    margin -= impact
                else:
                    margin += impact
        scenarios.append((weight, margin, float(base_sd)))
    return scenarios


def unresolved_star_availability(rotation: pd.DataFrame, team_ids: Iterable[int]) -> list[str]:
    if rotation is None or rotation.empty:
        return []
    ids = {str(v) for v in team_ids}
    unresolved = rotation[
        rotation["canonical_team_id"].astype(str).isin(ids)
        & rotation["role"].isin(["star", "starter"])
        & rotation["availability_probability"].between(0.05, 0.80, inclusive="both")
        & ~rotation["confirmed_starter"].fillna(False).astype(bool)
    ]
    return [
        str(row.get("player_name") or f"Player {row.get('canonical_player_id', '')}")
        for _, row in unresolved.iterrows()
    ]


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if any(pd.isna(v) for v in (lat1, lon1, lat2, lon2)):
        return 0.0
    radius = 3958.8
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp = math.radians(float(lat2) - float(lat1))
    dl = math.radians(float(lon2) - float(lon1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(max(1 - a, 0)))


def build_travel_context(schedule: pd.DataFrame, teams: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build one as-of-safe workload/travel row per team and game."""
    if schedule is None or schedule.empty:
        return pd.DataFrame()
    games = schedule.copy()
    games["_date"] = pd.to_datetime(games["game_date"], errors="coerce", utc=True)
    games = games.sort_values(["_date", "canonical_game_id"]).reset_index(drop=True)
    team_locations: dict[str, tuple[float, float]] = {}
    if teams is not None and not teams.empty:
        for _, team in teams.iterrows():
            team_locations[str(team.get("canonical_team_id"))] = (
                pd.to_numeric(team.get("latitude"), errors="coerce"),
                pd.to_numeric(team.get("longitude"), errors="coerce"),
            )

    team_history: dict[str, list[dict]] = {}
    rows: list[dict] = []
    for _, game in games.iterrows():
        home_id, away_id = str(game.get("home_team_id")), str(game.get("away_team_id"))
        neutral = bool(game.get("neutral_site", False))
        venue_lat = pd.to_numeric(game.get("venue_latitude"), errors="coerce")
        venue_lon = pd.to_numeric(game.get("venue_longitude"), errors="coerce")
        if pd.isna(venue_lat) or pd.isna(venue_lon):
            venue_lat, venue_lon = team_locations.get(home_id, (np.nan, np.nan))
        start = pd.to_datetime(game.get("scheduled_start"), errors="coerce", utc=True)
        local_hour = start.tz_convert("America/New_York").hour if pd.notna(start) else 19
        phase = str(game.get("season_phase") or game.get("season_type") or "").lower()
        cup = bool(game.get("is_commissioners_cup", False)) or "commissioner" in phase
        playoff = bool(game.get("is_playoff", False)) or "playoff" in phase

        for tid, is_home in ((home_id, True), (away_id, False)):
            history = team_history.setdefault(tid, [])
            prev = history[-1] if history else None
            game_date = game["_date"]
            rest = 3.0 if prev is None or pd.isna(game_date) else max((game_date - prev["date"]).days, 1)
            recent4 = sum((game_date - h["date"]).days <= 4 for h in history if pd.notna(game_date))
            recent7 = sum((game_date - h["date"]).days <= 7 for h in history if pd.notna(game_date))
            origin_lat, origin_lon = (
                (prev["lat"], prev["lon"]) if prev else team_locations.get(tid, (venue_lat, venue_lon))
            )
            miles = haversine_miles(origin_lat, origin_lon, venue_lat, venue_lon)
            tz_shift = abs(float(venue_lon) - float(origin_lon)) / 15.0 if not any(
                pd.isna(v) for v in (venue_lon, origin_lon)
            ) else 0.0
            rows.append({
                "league_key": game.get("league_key", "wnba"),
                "season": game.get("season"),
                "canonical_game_id": str(game.get("canonical_game_id", "")),
                "canonical_team_id": tid,
                "game_date": game.get("game_date"),
                "is_home": is_home,
                "rest_days": float(min(rest, 14)),
                "games_last_4_days": int(recent4),
                "games_last_7_days": int(recent7),
                "travel_miles": round(miles, 1),
                "timezone_shift_hours": round(tz_shift, 1),
                "is_cross_country": bool(miles >= 1500 or tz_shift >= 2.5),
                "is_early_start": bool(local_hour < 15),
                "is_commissioners_cup": cup,
                "is_playoff": playoff,
                "neutral_site": neutral,
                "observed_at": game.get("retrieved_at"),
            })
            history.append({"date": game_date, "lat": venue_lat, "lon": venue_lon})
    return pd.DataFrame(rows)


def context_labels(home_context: pd.Series | dict, away_context: pd.Series | dict) -> list[str]:
    labels: list[str] = []
    if bool(home_context.get("is_commissioners_cup", False)):
        labels.append("Commissioner's Cup")
    if bool(home_context.get("is_playoff", False)):
        labels.append("Playoffs")
    if bool(home_context.get("neutral_site", False)):
        labels.append("Neutral site")
    if bool(home_context.get("is_early_start", False)):
        labels.append("Early start")
    if bool(home_context.get("is_cross_country", False)) or bool(away_context.get("is_cross_country", False)):
        labels.append("Cross-country travel")
    if float(home_context.get("rest_days", 3)) <= 1 or float(away_context.get("rest_days", 3)) <= 1:
        labels.append("Back-to-back")
    return labels


def records_json(records: object) -> str:
    """Serialize UI provenance records without leaking pandas/numpy objects."""
    if isinstance(records, pd.DataFrame):
        records = records.to_dict("records")
    return json.dumps(records, default=str, separators=(",", ":"))


@dataclass(frozen=True)
class ScenarioSummary:
    margin_mean: float
    margin_sd: float
    scenario_uncertainty: float
    scenarios: int


def summarize_margin_scenarios(scenarios: Sequence[tuple[float, float, float]]) -> ScenarioSummary:
    mean, sd = mixture_prediction(scenarios)
    within = 0.0
    weights = np.asarray([max(float(w), 0.0) for w, _, _ in scenarios], dtype=float)
    weights = weights / weights.sum() if weights.sum() else np.repeat(1 / len(scenarios), len(scenarios))
    for weight, (_, _, scenario_sd) in zip(weights, scenarios):
        within += float(weight) * float(scenario_sd) ** 2
    between_sd = math.sqrt(max(sd**2 - within, 0.0))
    return ScenarioSummary(round(mean, 3), round(sd, 3), round(between_sd, 3), len(scenarios))
