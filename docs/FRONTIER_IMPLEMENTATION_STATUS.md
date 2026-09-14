# Frontier implementation status

This repository implements the actionable requirements in
`CURRENT_MODEL_BACKTEST_AUDIT_2026.md` and `FRONTIER_ENHANCEMENT_BLUEPRINT.md`.

## Current release state

The 2018-2025 artifact was retrained after backfilling 2023-2025 and scored on
327 untouched 2025 games. It remains paper-only until the production gate passes.
The staged gate reports `limited_paper` after 100 priced decisions across 40 games
with at least 25 decisions per market, while production still requires 300 priced
decisions, positive CLV, and clear drift checks. The UI presents limited evaluation
as monitoring-only and never enables live betting from that state.

## Requirement map

| Requirement | Implementation |
|---|---|
| Expanding-season folds and recency weighting | `utils/model_utils.py`, `scripts/train_models.py` |
| Separate winner/margin/total calibration | Distribution calibrators and reliability report in `utils/model_utils.py` |
| Untouched 2025 holdout and baselines | `scripts/train_models.py`, persisted `eval_metrics.json` |
| Market/CLV/ROI and frozen paper ledger | `utils/evaluation.py`, `scripts/replay_predictions.py` |
| Drift suspension and production gate | `utils/model_utils.py`, prediction no-bet policy |
| As-of news and odds observations | Schema v2 contracts and append-only stores in `utils/data_fetcher.py` |
| Minutes/availability partial pooling | `utils/scenario_engine.py` |
| Rest, workload, travel, score/return context | `utils/scenario_engine.py`, arena reference metadata |
| Lineups, play-by-play, officials, tracking | Canonical contracts and adapter/fetcher boundaries |
| Expansion and rookie cold starts | Hierarchical team/player priors |
| Rotation editor, context timeline, lineup view | `pages/1_Game_Predictions.py` |
| Source-health panel | `pages/7_Data_Health.py` |
| Props, parlays, futures, no Kelly | `utils/market_simulation.py`, `pages/2_Scenario_Lab.py` |
| Edge-case adapter fixtures | `scripts/validate_contract_fixtures.py` |
| Morning/injury/pre-tip replay | `scripts/replay_predictions.py` and daily workflow |
| Context-segment evaluation | Persisted `segment_performance` and the performance page |

## Verification

- `python -m compileall -q -f -x data_files .`
- `python scripts/validate_contract_fixtures.py`
- `python scripts/test_playwright.py` against an isolated Streamlit server

The same checks run in `.github/workflows/wnba-ci.yml`.
