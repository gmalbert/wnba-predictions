# 00 — Current State Audit

> **Purpose.** Phase-0 inventory of the existing Streamlit WNBA Predictions app
> ahead of the React + precomputed-JSON migration described in
> `docs/WNBA_CLOUDFLARE_REACT_CONVERSION.md` §46. Everything below is taken
> from the source code at the time of audit; no behaviour has been changed.
>
> **Audience.** Any working agent that picks up the migration needs the table
> in §2 to know where each Streamlit page reads from, what it computes, and
> what the React port must consume.

---

## 1. Stack and entry points

- **Frontend.** Python / Streamlit (≥1.51), Plotly via `st.line_chart`,
  pandas DataFrames displayed with `st.dataframe`, HTML/CSS injected via
  ``st.markdown(..., unsafe_allow_html=True)``.
- **Modelling.** scikit-learn, XGBoost, optional LightGBM, an in-house Elo
  system. All artefacts (model pickles, distribution calibrators, evaluation
  metrics) live in `data_files/wnba/model_artifacts/`.
- **Data ingestion.** Adapters under `utils/adapters/` for `wehoop`, `espn`,
  `wnba_stats`, `the_odds_api`, `odds_api_io`, `therundown`, `balldontlie`.
  Source priority is declared in `utils/source_registry.py`.
- **Canonical schemas.** `utils/data_contracts.py` defines 16 column lists
  (`GAMES_COLUMNS`, `TEAM_GAME_COLUMNS`, `PLAYER_GAME_COLUMNS`,
  `PREDICTION_COLUMNS`, `BET_LEDGER_COLUMNS`, etc.) and `SCHEMA_VERSION = "2.0.0"`.
- **Entry points.**
  - `predictions.py` → home dashboard (`st.navigation` is defined here).
  - `pages/1_Game_Predictions.py` through `pages/7_Data_Health.py` — seven
    sub-pages, each with `st.set_page_config` + `add_sidebar_logo()`.
- **Schedules.** `.github/workflows/wnba-ci.yml`, `wnba-daily-refresh.yml`,
  `wnba-odds-snapshot.yml`.
- **Tests.** `tests/test_odds_adapters.py` (pytest). End-to-end browser test
  is `scripts/test_playwright.py`.

---

## 2. Page-by-page audit

Format follows §48 of the conversion runbook:

| Feature | Current Streamlit file | Data source | Request-time Python? | Can precompute? | Can browser handle? | Backend required? | Target implementation |
|---|---|---|---|---|---|---|---|
| Header / logo / season date | `predictions.py` (`home_page`) | `data_files/logo.png`, `utils.league_config` | Yes (renders current date) | Yes | Yes (browser clock) | No | React `Home.tsx` reads `manifest.json` + uses browser time |
| Hero metrics (5 KPI tiles) | `predictions.py` | `load_predictions()` + `load_eval_metrics()` | Yes (pandas + `clip/apply`) | Yes (already precomputed in parquet) | Yes (arithmetic on JSON) | No | React `Home.tsx` reads `predictions.json` + `model_performance.json` |
| Upcoming matchup cards + prob bars | `predictions.py` | `load_predictions()` | Yes (`iterrows`, `_prob_bar_html`) | Yes | Yes | No | React `Home.tsx` + `ProbabilityBar.tsx` |
| Explore navigation tiles | `predictions.py` | static `st.page_link` | Yes (Streamlit routing) | Yes | Yes | No | React Router `Link` |
| Game Predictions list (per-game cards) | `pages/1_Game_Predictions.py` | `load_predictions()` + JSON columns | Yes (`iterrows`, `st.tabs`, `st.data_editor`) | Yes — but the rotation editor must remain browser-side | Yes (editor + recalculation) | No | React `GamePredictions.tsx` + `RotationEditor.tsx` using ported `scenario_engine` logic |
| Rotation/availability scenario editor | `pages/1_Game_Predictions.py` (`_availability_editor`) | `game.availability_json` + `utils.scenario_engine` | Yes (builds margin scenarios live) | Partially | Yes — port `build_margin_scenarios` + `summarize_margin_scenarios` to TypeScript | No | React `RotationEditor.tsx` with TS ports |
| Lineup matchup tab | `pages/1_Game_Predictions.py` (`_lineup_view`) | `game.lineup_matchup_json` | Yes (DataFrame render) | Yes | Yes | No | React tab |
| Travel & workload tab | `pages/1_Game_Predictions.py` (`_workload_view`) | `game.travel_context_json` | Yes | Yes | Yes | No | React tab |
| Provenance JSON tab | `pages/1_Game_Predictions.py` | `game` columns | Yes | Yes | Yes | No | React tab |
| Player-prop calculator | `pages/2_Scenario_Lab.py` (`prop_tab`) | `utils.market_simulation.simulate_player_prop` | Yes (50k Monte Carlo draws) | Partially — must run on input change | Yes — port the simulator | No | React `ScenarioLab.tsx` with TS port `simulatePlayerProp` + parity fixture |
| Correlated-parlay simulator | `pages/2_Scenario_Lab.py` (`parlay_tab`) | `simulate_correlated_parlay` | Yes (100k draws) | Partially | Yes — port | No | React `ScenarioLab.tsx` with TS port |
| Staking-policy tab | `pages/2_Scenario_Lab.py` (`policy_tab`) | `load_eval_metrics().release_gate` + `staking_policy` | Yes (JSON render) | Yes | Yes | No | React tab reads `release_gate.json` |
| Standings tables (per-conference) | `pages/3_Standings.py` | `get_standings(season)` (WNBA Stats) | Yes (groupby + sort) | Yes | Yes (sort/filter) | No | React `Standings.tsx` reads `standings.json` (browse by season) |
| Team recent form + game log + line chart | `pages/4_Team_Stats.py` | `get_team_game_stats`, `engineer_team_features` | Yes (rolling feature engineering) | Yes — features already engineered in pipeline | Yes — render | No | React `TeamStats.tsx` reads `team_stats.json` (per-team summary, recent_games, trend series) |
| Player summary, per-40 rates, game log | `pages/5_Player_Stats.py` | `get_player_game_stats` | Yes (per-40 normalization) | Yes | Yes | No | React `PlayerStats.tsx` reads `player_stats.json` (per-player summary, recent_games, trend series) |
| Release gate, calibration, distributions | `pages/6_Model_Performance.py` | `load_eval_metrics()` | Yes | Yes | Yes (charts) | No | React `ModelPerformance.tsx` reads `model_performance.json` |
| Walk-forward folds, market baselines, paper ledger, drift | `pages/6_Model_Performance.py` | `load_eval_metrics()`, `load_bet_ledger()` | Yes | Yes | Yes | No | React `ModelPerformance.tsx` (same JSON) |
| Source health table | `pages/7_Data_Health.py` (`load_health`) | `data_files/wnba/source_health.json` | Yes | Yes | Yes | No | React `DataHealth.tsx` reads `data_health.json` |
| Capability/fallback registry | `pages/7_Data_Health.py` | `SOURCE_PRIORITY` from `utils/source_registry` | Yes (hard-coded dict) | Yes | Yes | No | React `DataHealth.tsx` reads `data_health.json` (which contains a `capability_registry` field) |
| Artifact safety cards | `pages/7_Data_Health.py` | `load_eval_metrics().release_gate` + `league_config` | Yes | Yes | Yes | No | React |
| Sidebar (logo + nav) | `st.set_page_config` + `st.sidebar` | n/a | Yes | Yes | Yes | No | React Router layout (`AppShell.tsx`) |
| Footer ("Powered by Betting Oracle") | `footer.add_betting_oracle_footer` | static HTML | Yes | Yes | Yes | No | React `Footer.tsx` |

---

## 3. Data flow inventory

```
Wnba Stats / ESPN / wehoop / BALLDONTLIE / odds_api_io / TheRundown
                              ↓
            utils/adapters/* (per-source fetchers)
                              ↓
            utils/data_fetcher.* (cache + health-record)
                              ↓
            data_files/wnba/normalized/<dataset>/...
                              ↓
   ┌──────────────────────┬──────────────────────┬──────────────────────┐
   ↓                      ↓                      ↓                      ↓
team_game_stats      player_game_stats       schedule            standings
   │                      │                      │                      │
   └──────────┬───────────┴──────────────────────┴──────────────────────┘
              ↓
   utils/feature_engine.build_training_dataset (training only — not run by app)
              ↓
   utils/prediction_engine.generate_and_store_predictions
              ↓
   data_files/wnba/predictions/predictions_YYYY-MM-DD[_stage].parquet
              ↓
   load_predictions() / load_health() / load_eval_metrics()
              ↓
   Streamlit pages (predictions.py + pages/*.py)
```

The Streamlit pages perform *no* model training and *no* live inference during
page render — all heavy computation is in `scripts/`. This makes the React
migration straightforward: every page reads from a precomputed parquet that
can be exported once to JSON.

---

## 4. Live computations that must move to TypeScript

The following pieces run inside `pages/*.py` and therefore have to be ported
to TypeScript for the React app (or re-executed in the export step):

1. **Per-game rotation scenario editor** — `utils.scenario_engine.build_margin_scenarios`,
   `summarize_margin_scenarios`, `mixture_prediction`.
3. **Player-prop Monte Carlo** — `utils.market_simulation.simulate_player_prop` (50k
   draws, deterministic seed).
5. **Correlated-parlay Gaussian-copula** — `simulate_correlated_parlay` (100k
   draws, deterministic seed).

The first is interactive (must run in the browser when the user edits the
data editor); the latter two are calculator-style and run on every input
change. All three are seeded so they are exactly reproducible and can be
compared against a Python-generated fixture.

---

## 5. Inventory of secrets and live data paths

Secrets (must **not** enter the React bundle):

- `ODDS_API_IO_KEY` (used by `odds_api_io` adapter)
- `THERUNDOWN_API_KEY` (used by `therundown` adapter)
- `ODDS_API_KEY` (legacy `the_odds_api` adapter, prop odds)
- ESPN, wehoop, wnba_stats endpoints are unauthenticated but rate-limited

Live calls during render: **none** — every page reads from the cached parquet
files under `data_files/wnba/`. The Streamlit app does not hit the network
during a page render.

---

## 6. GitHub Actions workflows

```
.github/workflows/wnba-ci.yml            pytest + scripts/daily_update + scripts/train_models
.github/workflows/wnba-daily-refresh.yml full daily pipeline + commits data_files/
.github/workflows/wnba-odds-snapshot.yml periodic odds refresh
```

None of these are modified by this migration. The React export will be run
locally (`scripts/export_web_data.py`) and is not yet wired into CI as part
of Phases 0–5. (Wiring it into the daily workflow is Phase 6, which is
out of scope for this Goal.)