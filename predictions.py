"""WNBA Predictions — main entry point (Streamlit).

Dashboard-style landing page with today's matchups, best bets, model
performance, and navigation to the full app.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from footer import add_betting_oracle_footer
from utils.league_config import get_league_config

_CFG = get_league_config()
_ET = ZoneInfo("America/New_York")

st.set_page_config(
    page_title=f"WNBA Predictions",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

WNBA_RED = "#C8102E"  # WNBA red
WNBA_BLUE = "#1D428A"
CONF_COLORS = {"High": "#16a34a", "Medium": "#d97706", "Low": "#6b7280"}


def _prob_bar_html(home_prob: float, home: str, away: str) -> str:
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


def _conf_badge(tier: str) -> str:
    c = CONF_COLORS.get(tier, "#6b7280")
    return f'<span style="background:{c};color:white;padding:1px 9px;border-radius:10px;font-size:0.72rem;font-weight:700">{tier}</span>'


def home_page():
    """Dashboard landing page."""
    from utils.data_fetcher import load_predictions, get_team_game_stats, get_odds
    from utils.model_utils import load_eval_metrics

    # ── Header ────────────────────────────────────────────────────────────────
    hdr_left, hdr_right = st.columns([1, 4])
    with hdr_left:
        st.image("data_files/logo.png", width=130)
    with hdr_right:
        st.markdown(
            f"<h1 style='margin-bottom:0'>WNBA Predictions</h1>"
            f"<p style='color:#888;margin-top:2px'>Season {_CFG.current_season} · "
            f"{datetime.now(tz=_ET).strftime('%A, %B %d, %Y')}</p>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Load today's predictions (stored records; no live ML at render) ───────
    try:
        preds_df = load_predictions()
    except Exception:
        preds_df = pd.DataFrame()

    metrics = load_eval_metrics()

    # ── Hero metrics row ──────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    total_games = len(preds_df) if not preds_df.empty else 0
    high_conf = int((preds_df["confidence"] == "High").sum()) if not preds_df.empty else 0
    med_conf = int((preds_df["confidence"] == "Medium").sum()) if not preds_df.empty else 0
    avg_conv = (
        preds_df["home_win_prob"].clip(upper=0.99).apply(lambda p: max(p, 1 - p)).mean()
        if not preds_df.empty else 0.0
    )
    accuracy = metrics.get("win_model", {}).get("accuracy", None)

    m1.metric("Upcoming Games", total_games)
    m2.metric("High Confidence", high_conf)
    m3.metric("Medium Confidence", med_conf)
    m4.metric("Avg Conviction", f"{avg_conv:.0%}" if avg_conv else "—")
    m5.metric(
        "Model Accuracy",
        f"{accuracy:.1%}" if accuracy else "—",
        help="Ensemble accuracy on held-out games. Train via scripts/train_models.py.",
    )

    st.markdown("---")

    # ── Matchup cards ─────────────────────────────────────────────────────────
    if preds_df.empty:
        st.info("No upcoming games found, or data hasn't been generated yet. Run scripts/daily_update.py to populate.")
    else:
        st.markdown(f"### 🏀 Upcoming Matchups ({total_games})")
        for _, g in preds_df.iterrows():
            home = g.get("home_team", "Home")
            away = g.get("away_team", "Away")
            hp = float(g.get("home_win_prob", 0.5))
            conf = g.get("confidence", "Medium")
            spread = g.get("predicted_spread", None)

            spread_str = ""
            if spread is not None:
                try:
                    spread_val = float(spread)
                    fav = home if spread_val < 0 else away
                    spread_str = f"· {fav} -{abs(spread_val):.1f}"
                except (TypeError, ValueError):
                    pass

            with st.container(border=True):
                row_l, row_r = st.columns([5, 2])
                with row_l:
                    st.markdown(f"**{away}** @ **{home}** {spread_str}", unsafe_allow_html=True)
                    st.markdown(_prob_bar_html(hp, home, away), unsafe_allow_html=True)
                with row_r:
                    st.markdown(
                        f'<div style="text-align:right;padding-top:8px">{_conf_badge(conf)}</div>',
                        unsafe_allow_html=True,
                    )
                    fav_label = home if hp >= 0.5 else away
                    st.caption(f"Pick: {fav_label}")

    st.markdown("---")

    # ── Navigation tiles ──────────────────────────────────────────────────────
    st.markdown("### Explore")
    nc1, nc2, nc3, nc4, nc5 = st.columns(5)
    tiles = [
        ("🏀", "Game Predictions", "Matchups, edges & confidence", "pages/1_Game_Predictions.py"),
        ("🏆", "Standings", "League standings", "pages/3_Standings.py"),
        ("📊", "Team Stats", "Team metrics & trends", "pages/4_Team_Stats.py"),
        ("👤", "Player Stats", "Player dashboards", "pages/5_Player_Stats.py"),
        ("📈", "Model Performance", "Accuracy & calibration", "pages/6_Model_Performance.py"),
    ]
    for col, (icon, title, desc, path) in zip([nc1, nc2, nc3, nc4, nc5], tiles):
        with col:
            with st.container(border=True):
                st.markdown(f'<div style="text-align:center;font-size:1.6rem;padding-top:4px">{icon}</div>', unsafe_allow_html=True)
                st.page_link(path, label=f"**{title}**")
                st.caption(desc)

    add_betting_oracle_footer()


# ── Navigation ────────────────────────────────────────────────────────────────
pg = st.navigation(
    {
        "": [
            st.Page(home_page, title="Home", icon="🏠", default=True),
        ],
        "Predictions": [
            st.Page("pages/1_Game_Predictions.py", title="Game Predictions", icon="🏀"),
        ],
        "Stats": [
            st.Page("pages/3_Standings.py", title="Standings", icon="🏆"),
            st.Page("pages/4_Team_Stats.py", title="Team Stats", icon="📊"),
            st.Page("pages/5_Player_Stats.py", title="Player Stats", icon="👤"),
        ],
        "Models": [
            st.Page("pages/6_Model_Performance.py", title="Model Performance", icon="📈"),
            st.Page("pages/7_Data_Health.py", title="Data Health", icon="🩺"),
        ],
    }
)
pg.run()
