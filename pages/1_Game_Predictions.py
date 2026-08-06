"""Game Predictions — WNBA matchups, edges, and confidence.

Consumes stored prediction records (see scripts/generate_predictions.py) with
provenance: model version, feature schema, generated_at, and abstention states.
"""

import streamlit as st
import pandas as pd

from utils.data_fetcher import load_predictions, get_odds, load_health
from footer import add_sidebar_logo

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


st.title("🏀 Game Predictions")

preds = load_predictions()
if preds.empty:
    st.info("No stored predictions yet. Run `python scripts/generate_predictions.py` (or scripts/daily_update.py) to generate them.")
else:
    # Provenance banner
    col1, col2, col3 = st.columns(3)
    col1.metric("Model Version", preds["model_version"].iloc[0] if "model_version" in preds else "—")
    col2.metric("Feature Schema", preds["feature_schema_version"].iloc[0] if "feature_schema_version" in preds else "—")
    col3.metric("Generated At", str(preds["generated_at"].iloc[0])[:16] if "generated_at" in preds else "—")

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

        with st.container(border=True):
            c1, c2 = st.columns([3, 2])
            with c1:
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
