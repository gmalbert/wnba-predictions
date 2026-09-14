"""Game predictions, rotation scenarios, workload, and no-bet states."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import streamlit as st

from footer import add_betting_oracle_footer, add_sidebar_logo
from utils.data_fetcher import load_predictions
from utils.scenario_engine import build_margin_scenarios, summarize_margin_scenarios

st.set_page_config(page_title="Game Predictions", page_icon="🏀", layout="wide")
add_sidebar_logo()

WNBA_RED = "#C8102E"
WNBA_BLUE = "#1D428A"


def _json_records(value: object) -> list[dict]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _json_object(value: object) -> dict:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _prob_bar(home_prob: float, home: str, away: str) -> str:
    home_pct = round(home_prob * 100)
    away_pct = 100 - home_pct
    return (
        '<div style="display:flex;height:24px;border-radius:7px;overflow:hidden;'
        'font-size:.76rem;font-weight:700">'
        f'<div style="width:{home_pct}%;background:{WNBA_BLUE};color:white;display:flex;'
        f'align-items:center;justify-content:center">{home_pct}%</div>'
        f'<div style="width:{away_pct}%;background:{WNBA_RED};color:white;display:flex;'
        f'align-items:center;justify-content:center">{away_pct}%</div></div>'
        '<div style="display:flex;justify-content:space-between;font-size:.72rem;color:#888">'
        f'<span>{home}</span><span>{away}</span></div>'
    )


def _format_game_time(game: pd.Series) -> str:
    stamp = pd.to_datetime(game.get("scheduled_start"), errors="coerce", utc=True)
    if pd.isna(stamp):
        return str(game.get("game_date", ""))
    return stamp.tz_convert("America/New_York").strftime("%a, %b %d · %I:%M %p ET")


def _availability_editor(game: pd.Series, rotation: list[dict]) -> None:
    st.markdown("#### Rotation and availability scenario editor")
    st.caption(
        "Edit availability probability or active minutes to test a scenario. "
        "Edits are local to this browser session and never overwrite source observations."
    )
    if not rotation:
        st.info("No player-game history is available for a rotation scenario.")
        return
    frame = pd.DataFrame(rotation)
    visible = [
        column for column in [
            "player_name", "role", "status", "confirmed_starter",
            "availability_probability", "minutes_mean_if_active", "minutes_sd_if_active",
            "impact_per_minute",
        ] if column in frame.columns
    ]
    display_frame = frame[visible].copy()
    for column in ("player_name", "role", "status"):
        if column in display_frame:
            display_frame[column] = display_frame[column].astype(str).str.title()
    if "availability_probability" in display_frame:
        display_frame["availability_probability"] = (
            pd.to_numeric(display_frame["availability_probability"], errors="coerce") * 100
        ).round(1)
    edited = st.data_editor(
        display_frame,
        key=f"rotation_{game.get('game_id')}",
        width="stretch",
        hide_index=True,
        disabled=[column for column in visible if column not in {"availability_probability", "minutes_mean_if_active"}],
        column_config={
            "player_name": st.column_config.TextColumn("Player Name"),
            "role": st.column_config.TextColumn("Role"),
            "status": st.column_config.TextColumn("Status"),
            "confirmed_starter": st.column_config.CheckboxColumn("Confirmed Starter"),
            "availability_probability": st.column_config.NumberColumn("Play Probability", min_value=0.0, max_value=100.0, step=5.0, format="%.0f%%"),
            "minutes_mean_if_active": st.column_config.NumberColumn("Minutes If Active", min_value=0.0, max_value=50.0, step=1.0),
            "minutes_sd_if_active": st.column_config.NumberColumn("Minutes SD", format="%.1f"),
            "impact_per_minute": st.column_config.NumberColumn("Impact Per Minute", format="%.3f"),
        },
    )
    scenario_rotation = frame.copy()
    for column in ("availability_probability", "minutes_mean_if_active"):
        if column in edited:
            values = pd.to_numeric(edited[column], errors="coerce")
            if column == "availability_probability":
                values = values / 100.0
            scenario_rotation[column] = values.fillna(scenario_rotation[column])
    scenarios = build_margin_scenarios(
        float(game.get("margin_mean", 0.0)),
        float(game.get("margin_sd", 9.5)),
        scenario_rotation,
        int(game["home_team_id"]),
        int(game["away_team_id"]),
    )
    summary = summarize_margin_scenarios(scenarios)
    c1, c2, c3 = st.columns(3)
    c1.metric("Scenario home margin", f"{summary.margin_mean:+.1f}")
    c2.metric("Scenario margin SD", f"{summary.margin_sd:.1f}")
    c3.metric("Availability-only uncertainty", f"{summary.scenario_uncertainty:.1f} pts")
    market_spread = pd.to_numeric(game.get("market_spread"), errors="coerce")
    if pd.notna(market_spread) and summary.scenario_uncertainty > abs(-summary.margin_mean - market_spread):
        st.warning("No bet: the edited availability uncertainty is larger than the apparent spread edge.")


def _lineup_view(lineup: list[dict]) -> None:
    st.markdown("#### Lineup matchup and minutes uncertainty")
    if not lineup:
        st.info("No source lineup or inferred top-five rotation is available.")
        return
    frame = pd.DataFrame(lineup)
    cols = [column for column in ["side", "rank", "player", "player_ids", "minutes_mean", "minutes_sd", "role", "status", "net_rating"] if column in frame]
    st.dataframe(frame[cols], width="stretch", hide_index=True)


def _workload_view(context: dict) -> None:
    st.markdown("#### Travel and workload timeline")
    labels = context.get("labels", [])
    if labels:
        st.markdown(" · ".join(f"`{label}`" for label in labels))
    rows = []
    for side in ("away", "home"):
        row = context.get(side) or {}
        if row:
            rows.append({
                "team side": side.title(),
                "rest days": row.get("rest_days"),
                "games in 4 days": row.get("games_last_4_days"),
                "games in 7 days": row.get("games_last_7_days"),
                "travel miles": row.get("travel_miles"),
                "time-zone shift": row.get("timezone_shift_hours"),
                "cross-country": row.get("is_cross_country"),
                "early start": row.get("is_early_start"),
            })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    overseas = context.get("verified_overseas_workload", [])
    if overseas:
        st.markdown("**Verified overseas workload**")
        st.dataframe(pd.DataFrame(overseas), width="stretch", hide_index=True)
    else:
        st.caption("No verified overseas-workload observation is attached to this matchup.")


st.title("🏀 Game Predictions")
st.caption("Probabilistic projections with as-of availability, minutes, lineup, and workload context.")

predictions = load_predictions()
if predictions.empty:
    st.info("No stored predictions yet. Run `python scripts/generate_predictions.py --stage pre_tip`.")
else:
    gate_status = str(predictions.get("release_gate_status", pd.Series(["shadow_only"])).iloc[0])
    if gate_status == "limited_paper":
        st.warning(
            "Limited paper evaluation only. The model has enough evidence for monitoring, "
            "but live betting remains disabled until the full production gate passes."
        )
    elif gate_status != "production_ready":
        st.error(
            "Paper-only shadow mode. The production gate requires an untouched 2025 holdout, "
            "at least 300 priced paper bets, positive closing-line value, and clear drift checks."
        )

    for _, game in predictions.iterrows():
        home, away = str(game.get("home_team", "Home")), str(game.get("away_team", "Away"))
        home_prob = float(game.get("home_win_prob", 0.5))
        status = str(game.get("status", "no_bet"))
        with st.container(border=True):
            left, right = st.columns([3, 2])
            with left:
                st.caption(_format_game_time(game))
                st.markdown(f"### {away} @ {home}")
                st.markdown(_prob_bar(home_prob, home, away), unsafe_allow_html=True)
            with right:
                if status != "ready" or bool(game.get("paper_only", True)):
                    st.error("NO BET · PAPER ONLY")
                    st.caption(str(game.get("no_bet_reason") or "Release gate has not passed."))
                else:
                    st.success(f"{game.get('confidence', 'Low')} confidence")
                st.caption(f"Snapshot: {game.get('stage', 'unknown')} · {game.get('generated_at', '')}")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Home win", f"{home_prob:.1%}")
            c2.metric(
                "Home margin",
                f"{float(game.get('margin_mean', 0)):+.1f}",
                help=f"90% interval: {float(game.get('margin_low', 0)):+.1f} to {float(game.get('margin_high', 0)):+.1f}",
            )
            c3.metric(
                "Total",
                f"{float(game.get('total_mean', 0)):.1f}",
                help=f"90% interval: {float(game.get('total_low', 0)):.1f} to {float(game.get('total_high', 0)):.1f}",
            )
            c4.metric("Scenario uncertainty", f"{float(game.get('scenario_uncertainty', 0)):.1f} pts")

            market = st.columns(4)
            market[0].caption(
                f"De-vigged market home probability: {float(game['market_home_prob']):.1%}"
                if pd.notna(game.get("market_home_prob")) else "De-vigged market probability: —"
            )
            market[1].caption(
                f"Market home spread: {float(game['market_spread']):+.1f}"
                if pd.notna(game.get("market_spread")) else "Market spread: —"
            )
            market[2].caption(
                f"Market total: {float(game['market_total']):.1f}"
                if pd.notna(game.get("market_total")) else "Market total: —"
            )
            market[3].caption(
                f"Edge vs market: {float(game['edge']):+.1%}"
                if pd.notna(game.get("edge")) else "Edge vs market: —"
            )

            rotation = _json_records(game.get("availability_json"))
            lineup = _json_records(game.get("lineup_matchup_json"))
            context = _json_object(game.get("travel_context_json"))
            tab_rotation, tab_lineup, tab_workload, tab_provenance = st.tabs(
                ["Rotation scenario", "Lineup matchup", "Travel & context", "Provenance"]
            )
            with tab_rotation:
                _availability_editor(game, rotation)
            with tab_lineup:
                _lineup_view(lineup)
            with tab_workload:
                _workload_view(context)
            with tab_provenance:
                st.json({
                    "model_version": game.get("model_version"),
                    "feature_schema_version": game.get("feature_schema_version"),
                    "release_gate_status": game.get("release_gate_status"),
                    "availability_status": game.get("availability_status"),
                    "stage": game.get("stage"),
                    "generated_at": game.get("generated_at"),
                })

st.markdown("---")
st.caption("Informational analysis only. The application never recommends Kelly staking while the release gate is closed.")
add_betting_oracle_footer()
