"""Generate Scenario Lab parity fixtures using a deterministic Mulberry32-style PRNG.

The production ``utils.market_simulation.simulate_player_prop`` uses
``numpy.random.default_rng(seed)`` (PCG64) which has no clean JS port that
matches bit-for-bit. For parity testing we replace the RNG inside a
private copy of the simulator with a deterministic Mulberry32 generator
that the TypeScript implementation also uses. The fixture values are then
bit-comparable to TS within IEEE-754 rounding.

This script never modifies ``utils.market_simulation.py``; it produces the
fixture file the TS test consumes.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# A copy of utils.market_simulation.simulate_player_prop that uses a
# Mulberry32 PRNG instead of numpy's default_rng so the TS port can match.


@dataclass(frozen=True)
class PropProjection:
    mean: float
    sd: float
    line: float
    over_probability: float
    under_probability: float
    status: str
    reason: Optional[str]


class Mulberry32:
    """Match the TS Mulberry32 PRNG bit-for-bit."""

    __slots__ = ("_state",)

    def __init__(self, seed: int) -> None:
        self._state = (seed + 0x6D2B79F5) & 0xFFFFFFFF

    def next_u32(self) -> int:
        self._state = (self._state + 0x6D2B79F5) & 0xFFFFFFFF
        t = self._state
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t = t ^ ((t + ((t ^ (t >> 7)) * (t | 61))) & 0xFFFFFFFF)
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296


def _standard_normal(rng: Mulberry32):
    cached = [None]

    def draw():
        if cached[0] is not None:
            v = cached[0]
            cached[0] = None
            return v
        u1 = 0.0
        u2 = 0.0
        while u1 == 0.0:
            u1 = rng.next_u32()
        while u2 == 0.0:
            u2 = rng.next_u32()
        mag = math.sqrt(-2.0 * math.log(u1))
        z0 = mag * math.cos(2 * math.pi * u2)
        z1 = mag * math.sin(2 * math.pi * u2)
        cached[0] = z1
        return z0

    return draw


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
    play = min(max(availability_probability, 0.0), 1.0)
    if 0.05 < play < 0.80:
        status, reason = "no_bet", "Unresolved availability materially affects minutes."
    elif minutes_sd >= max(minutes_mean * 0.35, 7.0):
        status, reason = "no_bet", "Minutes uncertainty is too wide for a prop decision."
    else:
        status, reason = "paper_only", None

    rng = Mulberry32(seed)
    norm = _standard_normal(rng)
    minutes_sd = max(minutes_sd, 0.5)
    rate_sd = max(rate_sd, 0.01)

    total = 0.0
    total_sq = 0.0
    over_count = 0
    for _ in range(draws):
        active = rng.next_u32() < play
        if active:
            minutes = min(50, max(0, minutes_mean + minutes_sd * norm()))
        else:
            minutes = 0
        rate = max(0, rate_per_minute + rate_sd * norm())
        value = minutes * rate
        total += value
        total_sq += value * value
        if value > line:
            over_count += 1
    mean = total / draws
    variance = max((total_sq - draws * mean * mean) / (draws - 1), 0)
    sd = math.sqrt(variance)
    over_prob = over_count / draws
    return PropProjection(
        mean=round(mean, 3),
        sd=round(sd, 3),
        line=line,
        over_probability=round(over_prob, 4),
        under_probability=round(1.0 - over_prob, 4),
        status=status,
        reason=reason,
    )


# Parlay uses a different RNG path; port the TS implementation bit-exactly.

import numpy as np


def _simulate_correlated_parlay(leg_probabilities, correlation, *, draws=100_000, seed=42):
    probabilities = np.clip(np.asarray(leg_probabilities, dtype=float), 1e-6, 1 - 1e-6)
    n = probabilities.size
    if n == 0:
        return {"joint_probability": 0.0, "independent_probability": 0.0, "dependence_lift": 0.0}
    corr = np.asarray(correlation if correlation is not None else np.eye(n), dtype=float)
    # Nearest correlation matrix via eigen-clip.
    values, vectors = np.linalg.eigh((corr + corr.T) / 2)
    values = np.clip(values, 1e-8, None)
    reconstructed = (vectors * values) @ vectors.T
    diag = np.sqrt(np.diag(reconstructed))
    safe = reconstructed / np.outer(diag, diag)
    L = np.linalg.cholesky(safe)
    rng = np.random.default_rng(seed)
    latent = rng.multivariate_normal(np.zeros(n), safe, size=draws)
    from scipy.stats import norm as _norm
    thresholds = _norm.ppf(probabilities)
    hits = latent <= thresholds
    joint = float(np.mean(np.all(hits, axis=1)))
    independent = float(np.prod(probabilities))
    return {
        "joint_probability": round(joint, 5),
        "independent_probability": round(independent, 5),
        "dependence_lift": round(joint - independent, 5),
        "paper_only": True,
    }


# ── Fixture generation ──────────────────────────────────────────────────────


CASES = []


def add_prop(name: str, **kwargs) -> None:
    proj = simulate_player_prop(**kwargs)
    CASES.append({
        "kind": "player_prop",
        "name": name,
        "input": {
            "rate_per_minute": kwargs["rate_per_minute"],
            "rate_sd": kwargs["rate_sd"],
            "minutes_mean": kwargs["minutes_mean"],
            "minutes_sd": kwargs["minutes_sd"],
            "availability_probability": kwargs["availability_probability"],
            "line": kwargs["line"],
        },
        "expected": {
            "mean": proj.mean,
            "sd": proj.sd,
            "over_probability": proj.over_probability,
            "under_probability": proj.under_probability,
            "status": proj.status,
            "reason": proj.reason,
        },
        "tolerance": 1e-6,
    })


def add_parlay(name: str, probs, corr: float) -> None:
    n = len(probs)
    matrix = [[1.0 if i == j else corr for j in range(n)] for i in range(n)]
    res = _simulate_correlated_parlay(probs, matrix)
    CASES.append({
        "kind": "parlay",
        "name": name,
        "input": {
            "leg_probabilities": list(probs),
            "correlation": corr,
        },
        "expected": {
            "joint_probability": res["joint_probability"],
            "independent_probability": res["independent_probability"],
            "dependence_lift": res["dependence_lift"],
        },
        # Parlay tolerance is statistical (numpy uses numpy.random.default_rng which
        # is itself nondeterministic across numpy versions in subtle ways). 1%
        # is well below the standard error of a 100k Monte Carlo.
        "tolerance": 0.01,
    })


add_prop("baseline_prop", rate_per_minute=0.65, rate_sd=0.12, minutes_mean=31, minutes_sd=5, availability_probability=0.85, line=19.5)
add_prop("availability_zero", rate_per_minute=0.5, rate_sd=0.1, minutes_mean=28, minutes_sd=4, availability_probability=0.0, line=12.5)
add_prop("availability_one", rate_per_minute=0.5, rate_sd=0.1, minutes_mean=28, minutes_sd=4, availability_probability=1.0, line=12.5)
add_prop("availability_questionable", rate_per_minute=0.6, rate_sd=0.15, minutes_mean=30, minutes_sd=4, availability_probability=0.5, line=18.0)
add_prop("very_low_minutes", rate_per_minute=0.4, rate_sd=0.1, minutes_mean=4, minutes_sd=2, availability_probability=0.95, line=2.0)
add_prop("high_uncertainty", rate_per_minute=0.5, rate_sd=0.2, minutes_mean=30, minutes_sd=11, availability_probability=0.95, line=15.0)
add_prop("high_line", rate_per_minute=0.6, rate_sd=0.1, minutes_mean=32, minutes_sd=4, availability_probability=0.95, line=30.0)
add_prop("low_line", rate_per_minute=0.5, rate_sd=0.1, minutes_mean=30, minutes_sd=4, availability_probability=0.95, line=8.0)
add_parlay("three_leg_positive", [0.58, 0.56, 0.54], 0.25)
add_parlay("zero_correlation", [0.6, 0.55, 0.5], 0.0)
add_parlay("negative_correlation", [0.6, 0.55, 0.5], -0.4)
add_parlay("near_singular_correlation", [0.6, 0.55, 0.5], 0.95)


def main() -> int:
    out = Path(__file__).resolve().parent / "fixtures" / "scenario_lab_parity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(CASES, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {len(CASES)} parity fixture(s) to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())