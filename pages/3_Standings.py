"""Standings — WNBA league standings (dynamic conferences, calendar seasons)."""

import streamlit as st
import pandas as pd

from utils.data_fetcher import get_standings
from utils.league_config import get_league_config

st.set_page_config(page_title="Standings", page_icon="🏆", layout="wide")

_CFG = get_league_config()
season = st.sidebar.selectbox("Season", list(range(_CFG.current_season, _CFG.historical_start - 1, -1)))

st.title(f"🏆 WNBA Standings — {season}")

try:
    standings = get_standings(season)
except Exception:
    standings = pd.DataFrame()

if standings.empty:
    st.info("No standings data available. Run `python scripts/daily_update.py` to fetch.")
else:
    # ESPN standings frame has conference/team columns; WNBA Stats has its own.
    conf_col = "conference" if "conference" in standings.columns else None
    if conf_col and standings[conf_col].notna().any():
        for conf, grp in standings.groupby(conf_col):
            st.subheader(conf)
            display_cols = [c for c in ["team_name", "wins", "losses", "win_pct", "streak"] if c in grp.columns]
            if display_cols:
                st.dataframe(grp[display_cols].sort_values("wins", ascending=False).reset_index(drop=True), use_container_width=True)
    else:
        st.dataframe(standings, use_container_width=True)
