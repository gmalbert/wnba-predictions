"""Player Stats — WNBA player game logs, rolling averages, and per-40 rates.

Uses canonical player game stats. Smaller rosters and shorter seasons mean we
surface games/minutes thresholds and per-40 normalization (not per-48).
"""

import streamlit as st
import pandas as pd

from utils.data_fetcher import get_player_game_stats, get_team_game_stats
from utils.league_config import get_league_config
from utils.identity import load_players
from footer import add_sidebar_logo, add_betting_oracle_footer

st.set_page_config(page_title="Player Stats", page_icon="👤", layout="wide")
add_sidebar_logo()

_CFG = get_league_config()
season = st.sidebar.selectbox("Season", list(range(_CFG.current_season, _CFG.historical_start - 1, -1)), index=0)

st.title(f"👤 Player Stats — {season}")

try:
    pg = get_player_game_stats(season)
except Exception:
    pg = pd.DataFrame()

if pg.empty:
    st.info("No player game stats available. Run `python scripts/fetch_historical.py` to populate.")
    st.stop()

players = load_players()
player_map = {}
if not players.empty:
    player_map = dict(zip(players["canonical_player_id"], players["display_name"]))

player_ids = sorted(pg["canonical_player_id"].unique().tolist())
selected = st.selectbox(
    "Player",
    player_ids,
    format_func=lambda pid: player_map.get(pid, f"Player {pid}"),
)

player_df = pg[pg["canonical_player_id"] == selected].copy()
player_df["game_date"] = pd.to_datetime(player_df["game_date"])
player_df = player_df.sort_values("game_date")

# Per-40 rates
if "minutes" in player_df.columns:
    mins = pd.to_numeric(player_df["minutes"], errors="coerce").clip(lower=1)
    for col in ["points", "rebounds", "assists"]:
        if col in player_df.columns:
            player_df[f"{col}_per40"] = player_df[col] / mins * _CFG.normalization_minutes

# ── Summary metrics ───────────────────────────────────────────────────────────
recent = player_df.tail(10)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Games", len(player_df))
c2.metric("Pts/Game", f"{player_df['points'].mean():.1f}" if "points" in player_df else "—")
c3.metric("Pts/40 (L10)", f"{recent['points_per40'].mean():.1f}" if "points_per40" in recent else "—")
c4.metric("Ast/40 (L10)", f"{recent['assists_per40'].mean():.1f}" if "assists_per40" in recent else "—")

st.subheader("Recent Game Log")
show_cols = [c for c in ["game_date", "points", "rebounds", "assists", "minutes", "points_per40"] if c in player_df.columns]
st.dataframe(player_df[show_cols].tail(15).iloc[::-1], width="stretch")

if "points" in player_df.columns and len(player_df) >= 3:
    st.subheader("Points Per Game")
    st.line_chart(player_df[["game_date", "points"]].set_index("game_date"))

add_betting_oracle_footer()
