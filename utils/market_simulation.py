"""Uncertainty-aware player prop, parlay, and season-futures simulation.

All outputs are analytical/paper-only.  Staking is intentionally flat and the
module contains no Kelly sizing while the production release gate is closed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm


@dataclass(frozen=True)
class PropProjection:
    mean: float
    sd: float
    line: float
    over_probability: float
    under_probability: float
    status: str
    reason: str | None


def simulate_player_prop(
    *,
    rate_per_minute: float,
    rate_sd: float,
    minutes_mean: float,
    minutes_sd: float,
    line: float,
    availability_probability: float,
    draws: int = 50_000,
    seed: int = 42,
) -> PropProjection:
    """Prop distribution that integrates minutes and availability uncertainty."""
    play_probability = float(np.clip(availability_probability, 0.0, 1.0))
    if 0.05 < play_probability < 0.80:
        status = "no_bet"
        reason = "Unresolved availability materially affects minutes."
    elif minutes_sd >= max(minutes_mean * 0.35, 7.0):
        status = "no_bet"
        reason = "Minutes uncertainty is too wide for a prop decision."
    else:
        status, reason = "paper_only", None
    rng = np.random.default_rng(seed)
    active = rng.random(draws) < play_probability
    minutes = np.clip(rng.normal(minutes_mean, max(minutes_sd, 0.5), draws), 0, 50) * active
    rates = np.clip(rng.normal(rate_per_minute, max(rate_sd, 0.01), draws), 0, None)
    values = minutes * rates
    over = float(np.mean(values > line))
    return PropProjection(
        mean=round(float(np.mean(values)), 3),
        sd=round(float(np.std(values, ddof=1)), 3),
        line=float(line),
        over_probability=round(over, 4),
        under_probability=round(1.0 - over, 4),
        status=status,
        reason=reason,
    )


def nearest_correlation_matrix(matrix: np.ndarray) -> np.ndarray:
    """Project a symmetric matrix to a positive-semidefinite correlation matrix."""
    corr = np.asarray(matrix, dtype=float)
    corr = (corr + corr.T) / 2
    values, vectors = np.linalg.eigh(corr)
    values = np.clip(values, 1e-8, None)
    projected = vectors @ np.diag(values) @ vectors.T
    scale = np.sqrt(np.diag(projected))
    return projected / np.outer(scale, scale)


def simulate_correlated_parlay(
    leg_probabilities: list[float],
    correlation: np.ndarray | None = None,
    *,
    draws: int = 100_000,
    seed: int = 42,
) -> dict:
    """Estimate joint hit probability with a Gaussian copula."""
    probabilities = np.clip(np.asarray(leg_probabilities, dtype=float), 1e-6, 1 - 1e-6)
    if probabilities.size == 0:
        return {"joint_probability": 0.0, "independent_probability": 0.0, "dependence_lift": 0.0}
    corr = np.eye(len(probabilities)) if correlation is None else nearest_correlation_matrix(correlation)
    rng = np.random.default_rng(seed)
    latent = rng.multivariate_normal(np.zeros(len(probabilities)), corr, size=draws)
    hits = latent <= norm.ppf(probabilities)
    joint = float(np.mean(np.all(hits, axis=1)))
    independent = float(np.prod(probabilities))
    return {
        "joint_probability": round(joint, 5),
        "independent_probability": round(independent, 5),
        "dependence_lift": round(joint - independent, 5),
        "paper_only": True,
    }


def simulate_season_futures(
    teams: pd.DataFrame,
    remaining_games: pd.DataFrame,
    *,
    simulations: int = 20_000,
    playoff_teams: int = 8,
    seed: int = 42,
) -> pd.DataFrame:
    """Simulate wins/playoffs/title with rating and roster uncertainty.

    ``teams`` requires ``team_id``, ``wins``, and ``rating``; optional
    ``roster_sd`` widens the per-simulation rating. ``remaining_games``
    requires ``home_team_id`` and ``away_team_id``.
    """
    required_teams = {"team_id", "wins", "rating"}
    required_games = {"home_team_id", "away_team_id"}
    if teams is None or teams.empty or not required_teams.issubset(teams.columns):
        return pd.DataFrame(columns=["team_id", "expected_wins", "playoff_probability", "title_probability"])
    if remaining_games is None or not required_games.issubset(remaining_games.columns):
        remaining_games = pd.DataFrame(columns=list(required_games))
    table = teams.copy().reset_index(drop=True)
    ids = table["team_id"].astype(str).tolist()
    index = {team_id: i for i, team_id in enumerate(ids)}
    rng = np.random.default_rng(seed)
    base_wins = pd.to_numeric(table["wins"], errors="coerce").fillna(0).to_numpy(float)
    ratings = pd.to_numeric(table["rating"], errors="coerce").fillna(0).to_numpy(float)
    roster_sd = pd.to_numeric(table.get("roster_sd", 0.0), errors="coerce").fillna(0).to_numpy(float)
    wins = np.repeat(base_wins[None, :], simulations, axis=0)
    simulated_rating = rng.normal(ratings, np.maximum(roster_sd, 1e-6), size=(simulations, len(table)))
    for _, game in remaining_games.iterrows():
        home, away = index.get(str(game["home_team_id"])), index.get(str(game["away_team_id"]))
        if home is None or away is None:
            continue
        probability = 1.0 / (1.0 + np.exp(-(simulated_rating[:, home] - simulated_rating[:, away] + 0.15)))
        home_win = rng.random(simulations) < probability
        wins[:, home] += home_win
        wins[:, away] += ~home_win
    order = np.argsort(-wins, axis=1)
    playoff_hits = np.zeros_like(wins, dtype=bool)
    for simulation in range(simulations):
        playoff_hits[simulation, order[simulation, : min(playoff_teams, len(table))]] = True
    # A compact postseason proxy: title weight is softmax rating among qualifiers.
    title_hits = np.zeros_like(wins, dtype=float)
    for simulation in range(simulations):
        qualifiers = order[simulation, : min(playoff_teams, len(table))]
        weights = np.exp(simulated_rating[simulation, qualifiers] - simulated_rating[simulation, qualifiers].max())
        weights /= weights.sum()
        champion = rng.choice(qualifiers, p=weights)
        title_hits[simulation, champion] = 1.0
    return pd.DataFrame({
        "team_id": table["team_id"],
        "expected_wins": wins.mean(axis=0).round(2),
        "playoff_probability": playoff_hits.mean(axis=0).round(4),
        "title_probability": title_hits.mean(axis=0).round(4),
    })


def staking_policy(*, release_gate_passed: bool) -> dict:
    """Paper-only flat staking; Kelly remains disabled by design."""
    return {
        "live_stake_units": 0.0,
        "paper_stake_units": 1.0,
        "kelly_enabled": False,
        "reason": (
            "Production gate passed, but Kelly remains disabled until a separate staking review."
            if release_gate_passed
            else "Production release gate is closed."
        ),
    }

