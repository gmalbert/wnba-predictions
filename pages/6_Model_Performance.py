"""Release-gated WNBA model, distribution, market, CLV, and drift metrics."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from footer import add_betting_oracle_footer, add_sidebar_logo
from utils.evaluation import ledger_summary, load_bet_ledger
from utils.model_utils import load_eval_metrics, model_dir

st.set_page_config(page_title="Model Performance", page_icon="📈", layout="wide")
add_sidebar_logo()
st.title("📈 Model Performance")

metrics = load_eval_metrics()
if not metrics:
    st.info("No evaluation metrics yet. Run `python scripts/train_models.py`.")
    st.stop()

gate = metrics.get("release_gate", {})
st.subheader("Production release gate")
if gate.get("status") == "production_ready":
    st.success("Production release gate passed.")
else:
    st.error("Shadow/paper-only artifact. Live betting use is suspended.")
checks = gate.get("checks", {})
check_cols = st.columns(max(len(checks), 1))
for column, (name, passed) in zip(check_cols, checks.items()):
    column.metric(name.replace("_", " ").title(), "PASS" if passed else "FAIL")

st.caption(
    f"Rows: {metrics.get('n_rows', 0):,} · Seasons: {metrics.get('seasons', [])} · "
    f"Untouched holdout: {metrics.get('holdout_season', '—')} ({metrics.get('holdout_rows', 0):,} games)"
)

winner = metrics.get("win_model", {})
st.subheader("Untouched 2025 winner score")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Accuracy", f"{winner.get('accuracy', 0):.1%}")
c2.metric("Log loss", f"{winner.get('log_loss', 0):.3f}")
c3.metric("Brier score", f"{winner.get('brier_score', 0):.3f}")
c4.metric("Games", f"{winner.get('n_test', metrics.get('holdout_rows', 0)):,}")
calibration = metrics.get("winner_calibration", {})
if calibration:
    st.caption(
        f"Winner calibration: ECE {calibration.get('ece', 0):.3f} · "
        f"maximum calibration error {calibration.get('mce', 0):.3f}"
    )
    with st.expander("Winner reliability bins"):
        st.dataframe(pd.DataFrame(calibration.get("bins", [])), width="stretch", hide_index=True)

margin, totals = metrics.get("margin", {}), metrics.get("totals", {})
st.subheader("Calibrated continuous distributions")
distribution_rows = []
for label, values in (("Margin", margin), ("Total", totals)):
    if values:
        distribution_rows.append({
            "target": label,
            "MAE": values.get("mae"),
            "RMSE": values.get("rmse"),
            "CRPS": values.get("crps"),
            "90% coverage": values.get("interval_90_coverage"),
            "residual SD": values.get("residual_sd"),
        })
if distribution_rows:
    st.dataframe(pd.DataFrame(distribution_rows), width="stretch", hide_index=True)
else:
    st.info("No recent-season distribution score is available yet.")

folds = metrics.get("walk_forward", [])
if folds:
    st.subheader("Expanding-season folds with recency weighting")
    st.dataframe(pd.DataFrame(folds), width="stretch", hide_index=True)

st.subheader("Baselines and market-relative scoring")
baselines = metrics.get("baselines", {})
rows = []
for name in ("elo", "simple_efficiency"):
    values = baselines.get(name, {})
    if values:
        rows.append({"baseline": name.replace("_", " ").title(), **values})
market = baselines.get("market", {})
winner_market = market.get("winner", {})
if winner_market:
    rows.append({"baseline": "Model on priced games", **winner_market.get("model", {}), "n": winner_market.get("n_priced")})
    rows.append({"baseline": "De-vigged close", **winner_market.get("market", {}), "n": winner_market.get("n_priced")})
if rows:
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
else:
    st.info("No aligned recent-season market snapshots are available for comparison.")
if market.get("spread") or market.get("total"):
    st.dataframe(
        pd.DataFrame([
            {"market": name.title(), **values}
            for name, values in (("spread", market.get("spread", {})), ("total", market.get("total", {})))
            if values
        ]),
        width="stretch",
        hide_index=True,
    )

line_buckets = metrics.get("line_bucket_calibration", {})
if any(line_buckets.values()):
    st.subheader("Line-bucket calibration")
    left, right = st.columns(2)
    with left:
        st.caption("Spread")
        st.dataframe(pd.DataFrame(line_buckets.get("spread", [])), width="stretch", hide_index=True)
    with right:
        st.caption("Total")
        st.dataframe(pd.DataFrame(line_buckets.get("total", [])), width="stretch", hide_index=True)

st.subheader("2026 frozen paper ledger")
ledger_metrics = ledger_summary()
l1, l2, l3, l4 = st.columns(4)
l1.metric("Priced bets", ledger_metrics["priced_bets"], help="Release gate requires at least 300.")
l2.metric("Graded bets", ledger_metrics["graded_bets"])
l3.metric("Mean CLV", f"{ledger_metrics['mean_clv']:+.3f}" if ledger_metrics["mean_clv"] is not None else "—")
l4.metric("Flat-stake ROI", f"{ledger_metrics['roi']:.1%}" if ledger_metrics["roi"] is not None else "—")
if ledger_metrics["by_market"]:
    st.dataframe(pd.DataFrame(ledger_metrics["by_market"]), width="stretch", hide_index=True)
with st.expander("Frozen bet records"):
    ledger = load_bet_ledger()
    if ledger.empty:
        st.caption("The ledger is empty. Each prediction horizon freezes paper-only records automatically.")
    else:
        st.dataframe(ledger.sort_values("frozen_at", ascending=False), width="stretch", hide_index=True)

st.subheader("Drift and automatic suspension")
drift = metrics.get("drift", {})
if drift.get("suspended"):
    st.error(f"Suspended: maximum PSI is {drift.get('max_psi', 0):.3f} (threshold 0.25).")
else:
    st.success(f"Drift clear: maximum PSI is {drift.get('max_psi', 0):.3f}.")
warning_features = drift.get("warning_features", [])
if warning_features:
    st.caption("Shifted features: " + ", ".join(warning_features))

segments = metrics.get("segment_performance", {})
if segments:
    st.subheader("Performance by WNBA context")
    tabs = st.tabs([name.replace("_", " ").title() for name in segments])
    for tab, (name, records) in zip(tabs, segments.items()):
        with tab:
            if records:
                st.dataframe(pd.DataFrame(records), width="stretch", hide_index=True)
            else:
                st.caption(f"No {name.replace('_', ' ')} segments are available.")

st.caption(f"Artifacts: `{model_dir()}`")
add_betting_oracle_footer()
