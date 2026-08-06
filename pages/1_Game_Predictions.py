"""Game Predictions — WNBA matchups, edges, and confidence.

Consumes stored prediction records (see scripts/generate_predictions.py) with
provenance: model version, feature schema, generated_at, and abstention states.
"""

import streamlit as st
import pandas as pd

from utils.data_fetcher import load_predictions, get_odds, load_health
from footer import add_sidebar_logo, add_betting_oracle_footer

st.set_page_config(page_title="Game Predictions", page_icon="🏀", layout="wide")
add_sidebar_logo()

WNBA_RED = "#C8102E"
WNBA_BLUE = "#1D428A"


def _prob_bar(home_prob: float, home: str, away: str) -> str:
    hp = round(home_prob * 100)
    ap = 100 - hp
    return (
        f'<div style="display:flex;height:22px;border-radius:6px;overflow:hidden;font-size:0.75rem;font-weight:600">'
        f'<div style="width:{hp}%;background:{WNBA_BLUE};color:white;display:flex;align-items:center;justify-content:center">{hp}%</div>'
        f'<div style="width:{ap}%;background:{WNBA_RED};color:white;display:flex;align-items:center;justify-content:center">{ap}%</div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:0.7rem;color:#888;margin-top:2px">'
        f'<span>{home}</span><span>{away}</span></div>'
    )


def _format_game_time(g: pd.Series) -> str:
    """Format the scheduled start into a readable date + time string."""
    start = g.get("scheduled_start")
    if start is None or pd.isna(start):
        return ""
    try:
        ts = pd.to_datetime(start)
        # Convert to US/Eastern for display
        ts = ts.tz_convert("America/New_York") if ts.tzinfo else ts.tz_localize("UTC").tz_convert("America/New_York")
        return ts.strftime("%a, %b %d · %I:%M %p ET")
    except Exception:
        return ""


st.title("🏀 Game Predictions")

preds = load_predictions()
if preds.empty:
    st.info("No stored predictions yet. Run `python scripts/generate_predictions.py` (or scripts/daily_update.py) to generate them.")
else:
    # Abstention / status filter
    statuses = preds["status"].value_counts()
    for status, count in statuses.items():
        if status != "ready":
            st.warning(f"{count} game(s) in '{status}' state (insufficient history / missing data).")

    for _, g in preds.iterrows():
        home = g.get("home_team", "Home")
        away = g.get("away_team", "Away")
        hp = float(g.get("home_win_prob", 0.5))
        conf = g.get("confidence", "Medium")
        spread = g.get("predicted_spread")
        market_prob = g.get("market_home_prob")
        edge = g.get("edge")
        game_time = _format_game_time(g)

        with st.container(border=True):
            c1, c2 = st.columns([3, 2])
            with c1:
                if game_time:
                    st.caption(f"🕒 {game_time}")
                st.markdown(f"**{away}** @ **{home}**")
                st.markdown(_prob_bar(hp, home, away), unsafe_allow_html=True)
                if spread is not None and pd.notna(spread):
                    try:
                        sv = float(spread)
                        fav = home if sv < 0 else away
                        st.caption(f"Predicted spread: {fav} -{abs(sv):.1f}")
                    except (TypeError, ValueError):
                        pass
            with c2:
                st.markdown(f"**Confidence:** {conf}")
                if market_prob is not None and pd.notna(market_prob):
                    st.caption(f"Market home prob: {market_prob:.1%}")
                else:
                    st.caption("Market home prob: —")
                if edge is not None and pd.notna(edge):
                    st.caption(f"Edge vs market: {edge:+.1%}")
                else:
                    st.caption("Edge vs market: —")

st.markdown("---")
st.caption("Predictions are for informational purposes only. Past performance does not guarantee future results.")
add_betting_oracle_footer()
