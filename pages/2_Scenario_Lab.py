"""Paper-only prop, parlay-dependence, and futures scenario lab."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from footer import add_betting_oracle_footer, add_sidebar_logo
from utils.market_simulation import (
    simulate_correlated_parlay,
    simulate_player_prop,
    staking_policy,
)
from utils.model_utils import load_eval_metrics

st.set_page_config(page_title="Scenario Lab", page_icon="🧪", layout="wide")
add_sidebar_logo()
st.title("🧪 Scenario Lab")
st.error("Paper-only. Player props require minutes uncertainty; parlays use dependence simulation; Kelly is disabled.")

prop_tab, parlay_tab, policy_tab = st.tabs(["Player prop", "Parlay dependence", "Staking policy"])

with prop_tab:
    st.caption("This analytical calculator integrates the probability of playing and the player's minutes distribution.")
    c1, c2, c3 = st.columns(3)
    with c1:
        rate = st.number_input("Stat rate per minute", min_value=0.0, value=0.65, step=0.05)
        rate_sd = st.number_input("Rate SD", min_value=0.01, value=0.12, step=0.01)
    with c2:
        minutes = st.number_input("Expected minutes if active", min_value=0.0, value=31.0, step=1.0)
        minutes_sd = st.number_input("Minutes SD", min_value=0.5, value=5.0, step=0.5)
    with c3:
        availability = st.slider("Availability probability", 0.0, 1.0, 0.85, 0.05)
        line = st.number_input("Prop line", min_value=0.0, value=19.5, step=0.5)
    projection = simulate_player_prop(
        rate_per_minute=rate,
        rate_sd=rate_sd,
        minutes_mean=minutes,
        minutes_sd=minutes_sd,
        line=line,
        availability_probability=availability,
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Projected mean", f"{projection.mean:.1f}")
    m2.metric("Over probability", f"{projection.over_probability:.1%}")
    m3.metric("Under probability", f"{projection.under_probability:.1%}")
    if projection.status == "no_bet":
        st.warning(f"No bet: {projection.reason}")

with parlay_tab:
    st.caption("Positive correlation can materially change a multi-leg probability; independence is shown only as a comparator.")
    probabilities = [
        st.slider("Leg 1 probability", 0.05, 0.95, 0.58, 0.01),
        st.slider("Leg 2 probability", 0.05, 0.95, 0.56, 0.01),
        st.slider("Leg 3 probability", 0.05, 0.95, 0.54, 0.01),
    ]
    correlation = st.slider("Shared game/roster correlation", -0.50, 0.90, 0.25, 0.05)
    matrix = np.full((3, 3), correlation)
    np.fill_diagonal(matrix, 1.0)
    result = simulate_correlated_parlay(probabilities, matrix)
    p1, p2, p3 = st.columns(3)
    p1.metric("Simulated joint hit", f"{result['joint_probability']:.2%}")
    p2.metric("Independence estimate", f"{result['independent_probability']:.2%}")
    p3.metric("Dependence adjustment", f"{result['dependence_lift']:+.2%}")

with policy_tab:
    gate = load_eval_metrics().get("release_gate", {})
    policy = staking_policy(release_gate_passed=bool(gate.get("passed")))
    st.json(policy)
    st.caption("Season-futures simulation is available in `utils.market_simulation.simulate_season_futures` for pipeline use.")

add_betting_oracle_footer()
