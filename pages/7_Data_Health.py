"""Data Health — source status, freshness, and quality issues.

Surfaces source health records, quality checks, and model/schema versions so
data problems are visible rather than silent.
"""

import streamlit as st
import pandas as pd

from utils.data_fetcher import load_health
from utils.league_config import get_league_config
from utils.model_utils import load_eval_metrics, model_dir
from footer import add_sidebar_logo

st.set_page_config(page_title="Data Health", page_icon="🩺", layout="wide")
add_sidebar_logo()

_CFG = get_league_config()
st.title("🩺 Data Health")

health = load_health()
if not health:
    st.info("No source health records yet. Run `python scripts/publish_data_health.py` to populate.")
else:
    df = pd.DataFrame(health)
    display = df[["source", "data_type", "ok", "last_success", "last_attempt", "records"]]
    display["ok"] = display["ok"].map({True: "✅", False: "❌"})
    st.subheader("Source Status")
    st.dataframe(display.sort_values(["source", "data_type"]), width="stretch")

    failed = df[~df["ok"]]
    if not failed.empty:
        st.warning(f"{len(failed)} source/data-type combinations failed their last attempt:")
        for _, r in failed.iterrows():
            st.caption(f"- {r['source']} / {r['data_type']}: {r.get('error') or 'unknown error'}")

st.subheader("Artifacts")
c1, c2, c3 = st.columns(3)
c1.metric("League", _CFG.display_name)
c2.metric("Current Season", _CFG.current_season)
c3.metric("Regulation Minutes", _CFG.regulation_minutes)

metrics = load_eval_metrics()
if metrics:
    st.caption(f"Last training: {len(metrics.get('seasons', []))} seasons, {metrics.get('n_rows', 0):,} rows — `{model_dir()}`")
