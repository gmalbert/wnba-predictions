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
| **The Odds API** | WNBA moneylines, spreads, totals (requires `ODDS_API_KEY`) |
| **WNBA Stats** (nba_api) | League game logs via `league_id=10` (fallback) |

## WNBA-Specific Modeling

- Calendar-year seasons (no split-year `2025-26` formatting)
- Four 10-minute quarters — 40-minute regulation, per-40 normalization
- Dynamic team count (expansion-ready, no fixed 30-team assumptions)
- Leakage-safe features (`.shift(1)` rolling windows)
- Chronological walk-forward validation (no random game splits)
- Abstention states when data is insufficient or stale

```

## Disclaimer

Predictions are for informational/entertainment purposes only. Sports betting
involves risk; past performance does not guarantee future results.
