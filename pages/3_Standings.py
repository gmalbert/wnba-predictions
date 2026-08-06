"""Standings — WNBA league standings (dynamic conferences, calendar seasons)."""

import streamlit as st
import pandas as pd

from utils.data_fetcher import get_standings
from utils.league_config import get_league_config
from footer import add_sidebar_logo

st.set_page_config(page_title="Standings", page_icon="🏆", layout="wide")
add_sidebar_logo()

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
    # Normalize WNBA Stats columns (LeagueStandingsV3) to display-friendly names
    rename_map = {
        "TeamName": "team_name",
        "TeamCity": "team_city",
        "WINS": "wins",
        "LOSSES": "losses",
        "WIN_PCT": "win_pct",
        "Conference": "conference",
        "HomeRecord": "home_record",
        "RoadRecord": "road_record",
        "strCurrentStreak": "streak",
        "PlayoffRank": "playoff_rank",
    }
    standings = standings.rename(columns={k: v for k, v in rename_map.items() if k in standings.columns})
    if "team_name" not in standings.columns and "TeamName" in standings.columns:
        standings["team_name"] = standings["TeamName"]
    if "team_name" not in standings.columns and "team_city" in standings.columns:
        standings["team_name"] = standings["team_city"]

    conf_col = "conference" if "conference" in standings.columns else None
    if conf_col and standings[conf_col].notna().any():
        for conf, grp in standings.groupby(conf_col):
            st.subheader(conf)
            display_cols = [c for c in ["team_name", "wins", "losses", "win_pct", "streak", "playoff_rank"] if c in grp.columns]
            if display_cols:
                st.dataframe(grp[display_cols].sort_values("wins", ascending=False).reset_index(drop=True), width="stretch")
    else:
        display_cols = [c for c in ["team_name", "wins", "losses", "win_pct", "streak"] if c in standings.columns]
        if display_cols:
            st.dataframe(standings[display_cols].sort_values("wins", ascending=False).reset_index(drop=True), width="stretch")
        else:
            st.dataframe(standings, width="stretch")
