"""Standings — WNBA league standings (dynamic conferences, calendar seasons)."""

import streamlit as st
import pandas as pd

from utils.data_fetcher import get_standings
from utils.league_config import get_league_config
from footer import add_sidebar_logo, add_betting_oracle_footer

st.set_page_config(page_title="Standings", page_icon="🏆", layout="wide")
add_sidebar_logo()

_CFG = get_league_config()
season = st.sidebar.selectbox("Season", list(range(_CFG.current_season, _CFG.historical_start - 1, -1)))

st.title(f"🏆 WNBA Standings — {season}")

try:
    standings = get_standings(season)
except Exception:
    standings = pd.DataFrame()

# Display-friendly column mapping (source column -> (label, formatter))
COLUMN_SPECS = {
    "TeamName": ("Team", None),
    "WINS": ("Wins", None),
    "LOSSES": ("Losses", None),
    "WinPCT": ("Win %", lambda v: f"{v:.3f}"),
    "strCurrentStreak": ("Streak", None),
    "PlayoffRank": ("Playoff Rank", None),
    "Conference": ("Conference", None),
    "HOME": ("Home Record", None),
    "ROAD": ("Road Record", None),
    "L10": ("Last 10", None),
    "PointsPG": ("Points/Game", None),
    "OppPointsPG": ("Opp Points/Game", None),
    "DiffPointsPG": ("Point Diff", None),
}


def _build_display(df: pd.DataFrame) -> pd.DataFrame:
    """Build a display frame with title-case, underscore-free headers."""
    out = pd.DataFrame()
    for col, (label, fmt) in COLUMN_SPECS.items():
        if col in df.columns:
            series = df[col]
            if fmt:
                series = series.apply(fmt)
            out[label] = series
    return out


if standings.empty:
    st.info("No standings data available. Run `python scripts/daily_update.py` to fetch.")
else:
    conf_col = "Conference" if "Conference" in standings.columns else None
    if conf_col and standings[conf_col].notna().any():
        for conf, grp in standings.groupby(conf_col):
            st.subheader(conf)
            display = _build_display(grp)
            if not display.empty:
                sort_col = "Wins" if "Wins" in display.columns else display.columns[0]
                st.dataframe(
                    display.sort_values(sort_col, ascending=False).reset_index(drop=True),
                    width="stretch",
                    hide_index=True,
                )
    else:
        display = _build_display(standings)
        if not display.empty:
            sort_col = "Wins" if "Wins" in display.columns else display.columns[0]
            st.dataframe(
                display.sort_values(sort_col, ascending=False).reset_index(drop=True),
                width="stretch",
                hide_index=True,
            )
        else:
            st.dataframe(standings, width="stretch", hide_index=True)

add_betting_oracle_footer()
