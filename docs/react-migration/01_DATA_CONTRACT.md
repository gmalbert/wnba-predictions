# 01 — Data Contract

> **Purpose.** The single source of truth for the JSON artifacts that the
> React frontend reads. Every file is produced by
> `scripts/export_web_data.py` and validated by
> `scripts/validate_web_data.py`. The schema versions below let the React
> app reject incompatible data early.
>
> **Loading model.** React imports these via a single configurable
> `dataClient` (`VITE_DATA_BASE_URL`, default `/data/` for local dev). No
> other paths are used, and no network is touched by the frontend.

---

## Common envelope

Every JSON artifact carries:

```json
{
  "schema_version": 1,
  "generated_at": "<ISO-8601 UTC>",
  "league_key": "wnba"
}
```

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | Bump only when an incompatible field change ships |
| `generated_at` | string | UTC, ISO-8601, second precision |
| `league_key` | string | Always `"wnba"` for this app |

Missing values are **always** JSON `null`, never `NaN` / `Infinity` /
missing key. Timestamps are ISO-8601. IDs are strings unless they are
the deterministic SHA-256 hash prefixed ids used by the ledger (still
strings).

---

## `manifest.json`

The release manifest. React fetches this first; everything else references it.

```json
{
  "schema_version": 1,
  "generated_at": "2026-09-21T20:15:00Z",
  "league_key": "wnba",
  "sport": "WNBA",
  "season": 2026,
  "model_version": "wnba-ensemble-v2",
  "feature_schema_version": "2.0.0",
  "release_mode": "paper_only",
  "status": "ok",
  "artifacts": {
    "predictions":       "predictions.json",
    "standings":         "standings.json",
    "team_stats":        "team_stats.json",
    "player_stats":      "player_stats.json",
    "model_performance": "model_performance.json",
    "data_health":       "data_health.json",
    "release_gate":      "release_gate.json",
    "scenario_policy":   "scenario_policy.json"
  },
  "thresholds": {
    "predictions_stale_hours": 24,
    "standings_stale_hours":   168,
    "team_stats_stale_hours":  168,
    "model_perf_stale_hours":  720
  }
}
```

| Field | Type | Nullable | Consumer |
|---|---|---|---|
| `generated_at` | ISO-8601 string | no | freshness banner on every page |
| `season` | int | no | pages that filter by season |
| `release_mode` | enum: `paper_only`/`production` | no | global banner |
| `status` | enum: `ok`/`degraded`/`failed` | no | error-state rendering |
| `artifacts` | map filename | no | dataClient |
| `thresholds` | map int hours | no | per-dataset staleness |

`status`:
- `ok` → show as usual.
- `degraded` → show a yellow banner: "Data pipeline reported degradation;
  some sources may be stale."
- `failed` → show a red banner and disable filter UI.

---

## `predictions.json`

Authoritative copy of the latest full-schema prediction parquet file. The
React `Home` and `Game Predictions` pages render straight from this.

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "league_key": "wnba",
  "games": [
    {
      "prediction_id": "401857176_pre_tip_2026-08-26T01:30:53+00:00",
      "game_id": "401857176",
      "season": 2026,
      "game_date": "2026-08-26",
      "scheduled_start": "2026-08-26T23:00:00Z",
      "home_team": "Connecticut Sun",
      "away_team": "Golden State Valkyries",
      "home_team_id": 18,
      "away_team_id": 129689,
      "home_win_prob": 0.1778,
      "away_win_prob": 0.8222,
      "predicted_spread": 14.34,
      "predicted_total": 171.21,
      "margin_mean": -14.343,
      "margin_sd": 14.795,
      "margin_low": -38.681,
      "margin_high": 9.995,
      "total_mean": 171.213,
      "total_sd": 18.962,
      "total_low": 141.574,
      "total_high": 200.697,
      "market_home_prob": 0.1332,
      "market_spread": 13.375,
      "market_total": 150.5625,
      "edge": 0.0445,
      "confidence": "Medium",
      "status": "no_bet",
      "no_bet_reason": "Production release gate has not passed",
      "paper_only": true,
      "release_gate_status": "shadow_only",
      "scenario_uncertainty": 0.0,
      "availability_status": "resolved",
      "roster_continuity_home": 0.491,
      "roster_continuity_away": 0.573,
      "travel_context": { "home": { ... }, "away": { ... }, "labels": ["Cross-country travel"] },
      "availability": [
        { "player_id": "...", "team_id": 18, "player_name": "Leila...",
          "role": "star", "status": "Available", "confirmed_starter": true,
          "availability_probability": 0.99, "minutes_mean_if_active": 33.4,
          "minutes_sd_if_active": 3.2, "impact_per_minute": 0.085 }
      ],
      "lineup_matchup": [
        { "side": "home", "rank": 1, "player_id": "...", "player": "...",
          "minutes_mean": 33.4, "minutes_sd": 3.2, "role": "star",
          "status": "Available", "net_rating": null }
      ],
      "model_version": "wnba-ensemble-v2",
      "feature_schema_version": "2.0.0",
      "generated_at": "2026-08-26T01:30:53+00:00",
      "stage": "pre_tip"
    }
  ]
}
```

Notes:
- `home_win_prob + away_win_prob = 1.0` (rounded tolerance ≤ 1e-6).
- `availability_json` is parsed once and exposed as the typed array
  `availability`. Same for `lineup_matchup_json → lineup_matchup` and
  `travel_context_json → travel_context`.
- `release_gate_status` is duplicated per game so the React app can show
  per-game warnings without an extra fetch.

---

## `standings.json`

Per-season canonical standings from `data_files/wnba/normalized/standings/`.

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "league_key": "wnba",
  "season": 2026,
  "seasons_available": [2026, 2025, 2024, ...],
  "rows": [
    {
      "team_id": 1611661324,
      "team": "Minnesota Lynx",
      "city": "Minnesota",
      "wins": 25, "losses": 6, "win_pct": 0.806,
      "conference": "West", "playoff_rank": 1,
      "streak": "W 10",
      "home_record": "12-4", "road_record": "13-2", "l10": "10-0",
      "points_per_game": 92.7, "opp_points_per_game": 83.4, "point_diff": 9.4,
      "games_back": 0.0
    }
  ]
}
```

The React `Standings` page reads `seasons_available` for the season
selector and `rows` for the dataframe (grouped by `conference`).

---

## `team_stats.json`

Per-team season summary plus L10/trend series. Optimised for the React
`TeamStats` page; the full team-game parquet is not shipped.

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "league_key": "wnba",
  "season": 2026,
  "seasons_available": [...],
  "teams": {
    "20": {
      "team_id": 20,
      "name": "Atlanta Dream",
      "summary": {
        "games": 31,
        "win_pct_L10": 0.4,
        "points_L10": 81.2,
        "rest_days": 2,
        "streak": -2
      },
      "recent_games": [
        { "game_date": "2026-09-13", "opponent_team_id": 18,
          "is_home": 1, "points": 84, "win": 1 },
        ...
      ],
      "trends": [
        { "game_date": "2026-05-15", "points": 78, "points_L10": 79.1 },
        ...
      ],
      "rankings": {
        "off_rating_L10": 9, "tov_pct_L10": 4, "oreb_rate_L10": 7,
        "efg_pct_L10": 11
      }
    }
  }
}
```

---

## `player_stats.json`

Per-player summary + recent log + trends. Same `teams`/`players` split
principle: only what the page actually renders.

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "league_key": "wnba",
  "season": 2026,
  "seasons_available": [...],
  "players": {
    "3149391": {
      "player_id": 3149391,
      "name": "A'ja Wilson",
      "team_id": 1611661320,
      "summary": {
        "games": 31,
        "ppg": 27.3,
        "ppg_per40_L10": 30.1,
        "apg_per40_L10": 6.4
      },
      "recent_games": [
        { "game_date": "2026-09-13", "points": 28,
          "rebounds": 12, "assists": 4, "minutes": 33.4,
          "points_per40": 33.5 },
        ...
      ],
      "trends": [
        { "game_date": "2026-05-15", "points": 24 }
      ]
    }
  }
}
```

If a player has fewer than 3 games the `trends` field is omitted and the
page renders only the summary + recent log, matching the Streamlit
guard `if len(player_df) >= 3`.

---

## `model_performance.json`

A serialised copy of `data_files/wnba/model_artifacts/eval_metrics.json`,
minus the heavy per-bin frames beyond what's rendered. The React page
renders the same headline numbers, calibration bins, distributions,
walk-forward folds, baselines, line-bucket calibration, paper ledger
summary, drift report, and segment performance tabs.

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "league_key": "wnba",
  "artifact_status": "shadow_only",
  "release_gate": { ... },
  "win_model": { "accuracy": 0.6606, "log_loss": 0.6544, "brier_score": 0.2264, "n_test": 327 },
  "winner_calibration": {
    "ece": 0.0739, "mce": 0.3149,
    "bins": [
      { "lower": 0.0, "upper": 0.1, "n": 10, "mean_probability": 0.0851,
        "observed_rate": 0.4, "absolute_error": 0.3149 },
      ...
    ]
  },
  "holdout_2025": {
    "margin_distribution": { "mae": 11.638, "rmse": 14.983, "crps": 8.36,
      "interval_90_coverage": 0.826, "residual_sd": 12.377 },
    "total_distribution": { "mae": 15.126, "rmse": 19.169, "crps": 10.591,
      "interval_90_coverage": 0.887, "residual_sd": 18.745 }
  },
  "walk_forward": [
    { "accuracy": 0.6395, "log_loss": 0.651, "brier_score": 0.2269,
      "train_through": 2019, "test_season": 2020, "n_train": 442, "n_test": 147 }
  ],
  "baselines": {
    "elo": { "accuracy": 0.6697, "log_loss": 0.6384, "brier_score": 0.2224 },
    "simple_efficiency": { "accuracy": 0.6422, "log_loss": 0.6543, "brier_score": 0.2299 },
    "market": {}
  },
  "line_bucket_calibration": { "spread": [], "total": [] },
  "paper_ledger": {
    "priced_bets": 0, "graded_bets": 0, "mean_clv": null,
    "roi": null, "profit_units": 0.0, "by_market": []
  },
  "ledger": [
    { "ledger_id": "...", "prediction_id": "...", "game_id": "...",
      "game_date": "...", "frozen_at": "...", "horizon": "midday",
      "market": "moneyline", "selection": "Atlanta Dream",
      "model_probability": 0.74, "model_line": null, "book": "consensus",
      "price": null, "market_line": 0.887, "closing_price": null,
      "closing_line": null, "clv": null, "stake_units": 1.0, "profit_units": null,
      "result": null, "status": "open", "paper_only": true,
      "model_version": "..." }
  ],
  "drift": {
    "max_psi": 0.2439,
    "warning_features": [...],
    "suspended": false
  },
  "segment_performance": {
    "travel": [...], "rest": [...], "roster_continuity": [...],
    "season_phase": [...], "data_source": [...]
  },
  "margin": { "mae": 11.638, "rmse": 14.983, "crps": 8.36,
    "interval_90_coverage": 0.826, "residual_sd": 12.377 },
  "totals": { "mae": 15.126, "rmse": 19.169, "crps": 10.591,
    "interval_90_coverage": 0.887, "residual_sd": 18.745 },
  "seasons": [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
  "n_rows": 4,
  "holdout_season": 2025,
  "holdout_rows": 327
}
```

---

## `data_health.json`

Combines the source-health registry, the capability/fallback registry,
and the per-page freshness metadata. React `DataHealth` page renders this
file plus a runtime-computed `age_hours` (now − last_success).

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "league_key": "wnba",
  "sources": [
    { "source": "espn", "data_type": "schedule",
      "ok": true, "last_attempt": "...", "last_success": "...",
      "error": null, "records": 339 },
    ...
  ],
  "capability_registry": [
    { "data_type": "schedule", "priority": 1, "source": "wnba_stats" },
    { "data_type": "schedule", "priority": 2, "source": "espn" },
    ...
  ],
  "artifact_safety": {
    "league": "WNBA",
    "season": 2026,
    "schema": "2.0.0",
    "artifact": "Shadow Only"
  },
  "as_of_coverage": [
    { "dataset": "Odds",
      "required_history": "Morning, injury report, pre-tip, close",
      "policy": "Append-only timestamps" },
    ...
  ]
}
```

The `artifact` field in `artifact_safety` is the release-gate status with
`_` replaced by spaces and title-cased (e.g. `shadow_only` → `Shadow
Only`).

---

## `release_gate.json`

Authoritative release-gate result emitted by the Python pipeline. The
React app displays but never recomputes it.

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "league_key": "wnba",
  "status": "shadow_only",
  "passed": false,
  "paper_only": true,
  "checks": {
    "untouched_2025_holdout": true,
    "minimum_300_priced_bets": false,
    "positive_clv": false,
    "drift_clear": true
  },
  "holdout_season": 2025,
  "holdout_rows": 327,
  "priced_bets": 0,
  "mean_clv": null,
  "drift_suspended": false
}
```

---

## `scenario_policy.json`

The paper-only staking policy that the React `Scenario Lab → Staking
policy` tab displays. Always `kelly_enabled: false` and `live_stake_units:
0.0` while the release gate is closed.

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "league_key": "wnba",
  "release_gate_passed": false,
  "live_stake_units": 0.0,
  "paper_stake_units": 1.0,
  "kelly_enabled": false,
  "reason": "Production release gate is closed."
}
```

---

## Size budgets

Targets from §31 of the conversion runbook. The export script asserts these
in CI (`scripts/validate_web_data.py`):

| File | Target |
|---|---|
| `manifest.json` | < 25 KB |
| `predictions.json` | < 1 MB |
| `standings.json` | < 500 KB |
| `team_stats.json` | < 5 MB |
| `player_stats.json` | < 5 MB |
| `model_performance.json` | < 2 MB |
| `data_health.json` | < 500 KB |
| `release_gate.json` | < 50 KB |
| `scenario_policy.json` | < 10 KB |

Exceeding a budget by more than 50% is a validation failure (the
validator logs a warning and exits 0 unless the file is so large the
browser would obviously suffer — > 25 MB for any single artifact).