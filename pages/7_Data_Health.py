"""Adapter-driven source health, freshness, coverage, and artifact safety."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from footer import add_betting_oracle_footer, add_sidebar_logo
from utils.data_fetcher import load_health
from utils.league_config import get_league_config
from utils.model_utils import load_eval_metrics, model_dir
from utils.source_registry import SOURCE_PRIORITY

st.set_page_config(page_title="Data Health", page_icon="🩺", layout="wide")
add_sidebar_logo()

cfg = get_league_config()
st.title("🩺 Data Health")
st.caption("Source metadata drives this panel; missing and stale observations are never silently substituted.")

health = load_health()
if not health:
    st.info("No source-health records yet. Run `python scripts/publish_data_health.py`.")
else:
    frame = pd.DataFrame(health)
    now = pd.Timestamp.now(tz="UTC")
    success = pd.to_datetime(frame.get("last_success"), errors="coerce", utc=True)
    frame["age_hours"] = ((now - success).dt.total_seconds() / 3600).round(1)
    frame["status"] = frame["ok"].map({True: "Healthy", False: "Failed"}).fillna("Unknown")
    display_cols = ["source", "data_type", "status", "last_success", "last_attempt", "age_hours", "records", "error"]
    st.subheader("Adapter source status")
    st.dataframe(frame[[column for column in display_cols if column in frame]], width="stretch", hide_index=True)
    failed = frame[~frame["ok"].fillna(False)]
    if not failed.empty:
        st.warning(f"{len(failed)} source/data combinations failed their latest attempt.")

st.subheader("Capability and fallback registry")
registry_rows = []
for data_type, sources in SOURCE_PRIORITY.items():
    for priority, source in enumerate(sources, start=1):
        registry_rows.append({"data type": data_type, "priority": priority, "source": source})
st.dataframe(pd.DataFrame(registry_rows), width="stretch", hide_index=True)

metrics = load_eval_metrics()
gate = metrics.get("release_gate", {})
st.subheader("Artifact safety")
c1, c2, c3, c4 = st.columns(4)
c1.metric("League", cfg.display_name)
c2.metric("Season", cfg.current_season)
c3.metric("Schema", "2.0.0")
c4.metric("Artifact", gate.get("status", "shadow_only").replace("_", " ").title())
if gate.get("status") != "production_ready":
    st.error("Stale/unvalidated artifacts are automatically presented as no-bet, paper-only projections.")
if metrics:
    st.caption(
        f"Training coverage: {metrics.get('seasons', [])} · {metrics.get('n_rows', 0):,} rows · "
        f"Holdout: {metrics.get('holdout_season', '—')} · `{model_dir()}`"
    )

st.subheader("As-of coverage expectations")
st.dataframe(pd.DataFrame([
    {"dataset": "Odds", "required history": "Morning, injury report, pre-tip, close", "policy": "Append-only timestamps"},
    {"dataset": "Availability/news", "required history": "Every status observation and starter confirmation", "policy": "No later observation in replay"},
    {"dataset": "Player minutes", "required history": "Game-level minutes plus uncertainty", "policy": "Partially pooled cold starts"},
    {"dataset": "Overseas workload", "required history": "Minutes, return date, provenance", "policy": "Show only verified rows"},
    {"dataset": "Lineups/on-off", "required history": "Lineup minutes and possessions", "policy": "Inferred rotation if absent"},
]), width="stretch", hide_index=True)

add_betting_oracle_footer()
