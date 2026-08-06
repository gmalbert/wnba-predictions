"""Model Performance — WNBA-only metrics, calibration, walk-forward results.

Shows held-out accuracy, log loss, Brier score, and walk-forward fold results
from the training run. No NBA history is ever displayed.
"""

import streamlit as st
import pandas as pd

from utils.model_utils import load_eval_metrics, model_dir
from footer import add_sidebar_logo, add_betting_oracle_footer

st.set_page_config(page_title="Model Performance", page_icon="📈", layout="wide")
add_sidebar_logo()

st.title("📈 Model Performance")

metrics = load_eval_metrics()
if not metrics:
    st.info("No evaluation metrics yet. Train models with `python scripts/train_models.py`.")
    st.stop()

win = metrics.get("win_model", {})
c1, c2, c3 = st.columns(3)
c1.metric("Accuracy", f"{win.get('accuracy', 0):.1%}")
c2.metric("Log Loss", f"{win.get('log_loss', 0):.3f}")
c3.metric("Brier Score", f"{win.get('brier_score', 0):.3f}")

st.markdown(f"**Training rows:** {metrics.get('n_rows', 0):,}  |  **Seasons:** {metrics.get('seasons', [])}")

# ── Walk-forward folds ────────────────────────────────────────────────────────
wf = metrics.get("walk_forward", [])
if wf:
    st.subheader("Walk-Forward Validation (chronological)")
    st.dataframe(pd.DataFrame(wf), width="stretch")

# ── Margin / totals ───────────────────────────────────────────────────────────
m = metrics.get("margin", {})
t = metrics.get("totals", {})
if m or t:
    st.subheader("Regression Models")
    mc1, mc2, tc1, tc2 = st.columns(4)
    mc1.metric("Margin MAE", m.get("margin_mae", "—"))
    mc2.metric("Margin RMSE", m.get("margin_rmse", "—"))
    tc1.metric("Totals MAE", t.get("total_points_mae", "—"))
    tc2.metric("Totals RMSE", t.get("total_points_rmse", "—"))

st.caption(f"Artifacts stored in `{model_dir()}`")
add_betting_oracle_footer()
