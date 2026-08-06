"""Team Stats — WNBA team metrics, rolling averages, and rankings.

Uses canonical team game stats with per-40 normalization and dynamic team
selection (no fixed team-count assumptions).
"""

import streamlit as st
import pandas as pd

from utils.data_fetcher import get_team_game_stats, get_player_game_stats
from utils.feature_engine import engineer_team_features
from utils.league_config import get_league_config
from utils.identity import load_teams
from footer import add_sidebar_logo

st.set_page_config(page_title="Team Stats", page_icon="📊", layout="wide")
add_sidebar_logo()

_CFG = get_league_config()
season = st.sidebar.selectbox("Season", list(range(_CFG.current_season, _CFG.historical_start - 1, -1)), index=0)

st.title(f"📊 Team Stats — {season}")

try:
    tg = get_team_game_stats(season)
except Exception:
    tg = pd.DataFrame()

if tg.empty:
    st.info("No team game stats available. Run `python scripts/fetch_historical.py` to populate.")
    st.stop()

# Team selector from canonical reference
teams = load_teams()
team_options = sorted(tg["canonical_team_id"].unique().tolist())
team_name_map = {}
if not teams.empty:
    team_name_map = dict(zip(teams["canonical_team_id"], teams["display_name"]))
selected_id = st.selectbox(
    "Team",
    team_options,
    format_func=lambda tid: team_name_map.get(tid, f"Team {tid}"),
)

team_df = tg[tg["canonical_team_id"] == selected_id].copy()
team_df["game_date"] = pd.to_datetime(team_df["game_date"])
team_df = team_df.sort_values("game_date")

feats = engineer_team_features(team_df)

# ── Recent form metrics ───────────────────────────────────────────────────────
recent = feats.tail(1)
cols = st.columns(4)
cols[0].metric("Recent Win% (L10)", f"{recent['win_pct_L10'].iloc[0]:.0%}" if "win_pct_L10" in recent else "—")
cols[1].metric("Pts/Game (L10)", f"{recent['points_L10'].iloc[0]:.1f}" if "points_L10" in recent else "—")
cols[2].metric("Rest Days", f"{recent['rest_days'].iloc[0]:.0f}" if "rest_days" in recent else "—")
cols[3].metric("Streak", f"{recent['streak'].iloc[0]:+.0f}" if "streak" in recent else "—")

# ── Game log ──────────────────────────────────────────────────────────────────
st.subheader("Game Log")
log_cols = ["game_date", "opponent_team_id", "is_home", "points", "win"]
log_cols = [c for c in log_cols if c in team_df.columns]
display = team_df[log_cols].copy()
display["is_home"] = display["is_home"].map({1: "Home", 0: "Away"})
display["win"] = display["win"].map({1: "W", 0: "L"})
st.dataframe(display.tail(15).iloc[::-1], width="stretch")

# ── Rolling points chart ──────────────────────────────────────────────────────
st.subheader("Points Per Game (rolling)")
if {"points_L10", "points"}.issubset(feats.columns):
    chart = feats[["game_date", "points", "points_L10"]].copy()
    chart = chart.rename(columns={"points": "Game", "points_L10": "Rolling L10"})
    st.line_chart(chart.set_index("game_date"))
