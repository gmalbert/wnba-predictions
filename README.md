# WNBA Predictions 🏀

A Streamlit-powered analytics platform for WNBA game predictions — win probabilities,
predicted spreads, totals, and market edges — built as an independent WNBA port of
`gmalbert/nba-predictions` following the migration plans in `docs/`.

## Quick Start

```bash
# 1. Create + activate a virtual environment
python -m venv venv
.venv\Scripts\Activate.ps1        # Windows
source venv/bin/activate          # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env template and add your API key(s)
copy .env.example .env            # add ODDS_API_KEY (The Odds API)

# 4. Populate data (wehoop/ESPN historical + current season)
python scripts/bootstrap_reference_data.py   # teams + players reference
python scripts/fetch_historical.py           # team/player game stats
python scripts/fetch_odds.py                 # current odds snapshot
python scripts/fetch_injuries.py             # current injuries

# 5. Train models
python scripts/train_models.py

# 6. Generate predictions
python scripts/generate_predictions.py

# 7. Run the app
streamlit run predictions.py
```

## Features

- **Game Predictions** — Win probabilities, predicted spreads, market edges, confidence tiers
- **Standings** — League standings with dynamic conferences (calendar-year seasons)
- **Team Stats** — Rolling averages, per-40 metrics, trend charts
- **Player Stats** — Player game logs, per-40 rates, smaller-sample thresholds
- **Model Performance** — Accuracy, log loss, Brier, walk-forward validation
- **Data Health** — Source status, freshness, quality issues

## Architecture

```
predictions.py          # Main entry (Streamlit, multi-page navigation)
pages/                  # 1_Game_Predictions, 3_Standings, 4_Team_Stats,
                        # 5_Player_Stats, 6_Model_Performance, 7_Data_Health
utils/
├── adapters/           # wehoop, espn, wnba_stats, balldontlie, odds_api
├── data_fetcher.py     # Façade: caching, fallbacks, source health
├── data_contracts.py   # Canonical schemas (games, box scores, odds, ...)
├── feature_engine.py   # Shifted rolling features, per-40 normalization
├── identity.py         # Team/player ID resolution across sources
├── league_config.py    # Typed WNBA config (calendar seasons, 40-min games)
├── model_utils.py      # XGBoost/LightGBM ensemble, Elo, calibration
├── prediction_engine.py# Prediction generation with provenance/abstention
├── quality.py          # Data validation + freshness
└── source_registry.py  # Source priority/fallback policy
scripts/                # bootstrap, fetch, normalize, train, predict, health
.github/workflows/      # wnba-daily-refresh, wnba-odds-snapshot
```

## Data Sources

| Source | Role |
|--------|------|
| **wehoop-data** | Historical schedule/box scores (ESPN-backed parquet, 2003–2022) |
| **ESPN** | Current season schedule, rosters, injuries, officials |
| **The Odds API** | WNBA moneylines, spreads, totals (requires `ODDS_API_KEY`) |
| **WNBA Stats** (nba_api) | League game logs via `league_id=10` (fallback) |

Raw payloads are archived under `data_files/wnba/raw/`; normalized data under
`data_files/wnba/normalized/`; models under `data_files/wnba/model_artifacts/`.

## WNBA-Specific Modeling

- Calendar-year seasons (no split-year `2025-26` formatting)
- Four 10-minute quarters — 40-minute regulation, per-40 normalization
- Dynamic team count (expansion-ready, no fixed 30-team assumptions)
- Leakage-safe features (`.shift(1)` rolling windows)
- Chronological walk-forward validation (no random game splits)
- Abstention states when data is insufficient or stale

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `ODDS_API_KEY` | The Odds API — WNBA lines | Optional (enables edges) |

## Testing

```bash
python -m py_compile predictions.py utils/**/*.py pages/*.py scripts/*.py
# With the app running on :8501:
python scripts/test_playwright.py   # headless browser smoke test
```

## Disclaimer

Predictions are for informational/entertainment purposes only. Sports betting
involves risk; past performance does not guarantee future results.
