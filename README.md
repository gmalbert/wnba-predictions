<p align="center">
  <img src="data_files/logo.png" alt="WNBA Predictions Logo" width="300">
</p>

# WNBA Predictions 🏀

A Streamlit-powered analytics platform for WNBA game predictions — win probabilities,
predicted spreads, totals, and market edges — built as an independent WNBA port of
`gmalbert/nba-predictions` following the migration plans in `docs/`.


## Features

- **Game Predictions** — Win probabilities, predicted spreads, market edges, confidence tiers
- **Standings** — League standings with dynamic conferences (calendar-year seasons)
- **Team Stats** — Rolling averages, per-40 metrics, trend charts
- **Player Stats** — Player game logs, per-40 rates, smaller-sample thresholds
- **Model Performance** — Accuracy, log loss, Brier, walk-forward validation
- **Data Health** — Source status, freshness, quality issues


## Data Sources

| Source | Role |
|--------|------|
| **wehoop-data** | Historical schedule/box scores (ESPN-backed parquet, 2003–2022) |
| **ESPN** | Current season schedule, rosters, injuries, officials |
| **Odds-API.io** | Primary WNBA moneylines, spreads, and totals (requires `ODDS_API_IO_KEY`) |
| **TheRundown** | Secondary WNBA moneylines, spreads, and totals (requires `THERUNDOWN_API_KEY`) |
| **The Odds API** | Legacy/manual player-prop fallback only (requires `ODDS_API_KEY`) |
| **WNBA Stats** (nba_api) | League game logs via `league_id=10` (fallback) |

## WNBA-Specific Modeling

- Calendar-year seasons (no split-year `2025-26` formatting)
- Four 10-minute quarters — 40-minute regulation, per-40 normalization
- Dynamic team count (expansion-ready, no fixed 30-team assumptions)
- Leakage-safe features (`.shift(1)` rolling windows)
- Chronological walk-forward validation (no random game splits)
- Abstention states when data is insufficient or stale
- Expanding-season validation with recency weighting and an untouched 2025 holdout
- Separately calibrated winner, margin, and total distributions (including CRPS)
- As-of availability/minutes scenarios, lineup continuity, travel, rest, early starts,
  Commissionerâ€™s Cup/playoff labels, and expansion cold-start priors
- De-vigged market comparison, frozen flat-stake paper ledger, CLV/ROI reporting,
  feature drift suspension, and a production release gate

## Safety Status

The app stays in **shadow / paper-only** mode until all release checks pass:

1. the untouched 2025 holdout is present;
2. at least 300 priced paper bets are frozen;
3. mean closing-line value is positive; and
4. feature drift is below the automatic-suspension threshold.

Unresolved star availability, stale team/player inputs, or scenario uncertainty larger
than an apparent edge produces an accessible **No Bet** state. Kelly staking is disabled.

## Operations

```powershell
# Backfill the audited recent-season gap
python scripts/fetch_historical.py --seasons 2023,2024,2025

# Train through 2025 while scoring 2025 untouched
python scripts/train_models.py --seasons 2018,2019,2020,2021,2022,2023,2024,2025 --holdout-season 2025

# Freeze as-of shadow ledgers
python scripts/generate_predictions.py --stage morning
python scripts/generate_predictions.py --stage injury_report
python scripts/generate_predictions.py --stage pre_tip

# Historical horizon replay and edge-case contracts
python scripts/replay_predictions.py --season 2025
python scripts/validate_contract_fixtures.py

# Compile and browser verification
python -m compileall -q -f -x data_files .
python -m streamlit run predictions.py --server.port 8501
python scripts/test_playwright.py
```

Player-prop snapshots remain an explicit legacy-provider path while the new core-market
adapters are being validated:

```powershell
python scripts/fetch_odds.py --force --horizon pre_tip --include-props
```

## Disclaimer

Predictions are for informational/entertainment purposes only. Sports betting
involves risk; past performance does not guarantee future results.
