# WNBA Predictions — Detailed File Disposition Matrix

This matrix is the working checklist for every major current repository asset.

| Current Path | Disposition | Estimated Reuse | Required Action | Initial Phase |
|---|---|---:|---|---:|
| `predictions.py` | Refactor | 70% | WNBA branding, config, stored prediction records, source health | 0/6 |
| `footer.py` | Edit | 90% | Branding, methodology and betting disclaimer links | 0 |
| `requirements.txt` | Audit | 80% | Pin versions, add tests/schema validation, remove dead packages | 0 |
| `packages.txt` | Review | 100% or delete | Retain only if deployment needs system package | 0 |
| `.streamlit/config.toml` | Retain | 95% | Review theme and app settings | 0 |
| `.copilot-instructions.md` | Rewrite | 40% | WNBA architecture, canonical schemas, no NBA artifacts | 0 |
| `.github/copilot-instructions.md` | Rewrite | 40% | Same as above; avoid conflicting instruction files | 0 |
| `config/seasons.toml` | Rewrite | 20% | Calendar-year seasons and overrides | 0 |
| `data_files/historical/*` | Delete | 0% | NBA data cannot remain active | 0 |
| `data_files/best_bets_today.json` | Delete | 0% | NBA output | 0 |
| `models/*` | Delete | 0% | Retrain WNBA models | 0 |
| `utils/data_fetcher.py` | Major rewrite | 35% | Façade + source adapters + canonical normalization | 1/2 |
| `utils/feature_engine.py` | Refactor | 70% | Canonical fields, per-40 audit, remove hoopR joins | 3 |
| `utils/hoopr_fetcher.py` | Replace | 10% | New `wehoop` adapter | 7 |
| `utils/model_utils.py` | Reuse/refactor | 90% | League metadata and artifact validation | 4 |
| `utils/prediction_engine.py` | Reuse/refactor | 80% | Canonical inputs, abstention, provenance | 5 |
| `scripts/daily_update.py` | Refactor | 65% | WNBA source orchestration and validation | 5 |
| `scripts/debug_injury.py` | Replace/delete | 20% | New generic injury diagnostic | 6 |
| `scripts/export_best_bets.py` | Disable/refactor | 50% | Re-enable only after validation | 8 |
| `scripts/fetch_historical.py` | Rewrite | 45% | WNBA raw/normalized backfill | 2 |
| `scripts/fetch_historical_odds.py` | Refactor | 70% | WNBA sport key and canonical matching | 5 |
| `scripts/fetch_hoopr_data.py` | Replace | 15% | New `fetch_wehoop_data.py` | 7 |
| `scripts/inj_verify.py` | Replace | 25% | Canonical injury verification | 6 |
| `scripts/preload_cache.py` | Refactor | 70% | Required vs optional caches | 5 |
| `scripts/scrape_external.py` | Decompose | 30–50% | Source-specific adapters and fixtures | 2/7 |
| `scripts/train_models.py` | Refactor | 80% | WNBA data, chronological validation, model cards | 4 |
| `pages/1_Game_Predictions.py` | Refactor | 70% | WNBA predictions and provenance | 6 |
| `pages/2_Pick_6.py` | Disable first | 30–60% | Rebuild after player pipeline | 9 |
| `pages/3_Standings.py` | Refactor | 70% | WNBA standings and dynamic rules | 6 |
| `pages/4_Team_Stats.py` | Refactor | 80% | WNBA metrics and dynamic teams | 6 |
| `pages/5_Player_Stats.py` | Refactor | 70% | Canonical players, per-40, smaller sample display | 6 |
| `pages/6_Model_Performance.py` | Refactor | 85% | WNBA-only history and market baseline | 6 |
| `.github/workflows/nightly-pipeline.yml` | Refactor | 65% | WNBA steps, atomic publishing, season schedule | 5 |
| `.github/workflows/hoopr-daily.yml` | Replace | 20% | `wehoop-daily.yml` | 7 |
| `.github/workflows/odds-backfill.yml` | Refactor | 75% | WNBA dates and sport key | 5 |
| `.github/workflows/odds-snapshot.yml` | Refactor | 75% | WNBA cadence and market telemetry | 5 |
| `.github/workflows/referee-assignments.yml` | Disable/replace | 30% | Collection-only officials workflow | 7 |
| `docs/data_sources.md` | Rewrite | 30% | WNBA sources and audit results | 1 |
| `docs/features.md` | Refactor | 65% | WNBA-specific feature definitions | 3 |
| `docs/models.md` | Refactor | 75% | WNBA validation and baselines | 4 |
| `docs/predictions.md` | Refactor | 75% | Prediction stages and provenance | 5 |
| `docs/layout.md` | Refactor | 85% | WNBA branding and Data Health page | 6 |

---

## New Required Files

| New Path | Purpose |
|---|---|
| `config/league.toml` | Central WNBA rules |
| `config/sources.toml` | Primary/fallback source policy |
| `config/feature_flags.toml` | Disable incomplete modules |
| `utils/league_config.py` | Typed league configuration |
| `utils/data_contracts.py` | Canonical schemas |
| `utils/identity.py` | Team/player ID resolution |
| `utils/quality.py` | Data validation and freshness |
| `utils/source_registry.py` | Source capability and priority |
| `utils/adapters/base.py` | Adapter protocol |
| `utils/adapters/wnba_stats.py` | Official Stats adapter |
| `utils/adapters/espn.py` | ESPN adapter |
| `utils/adapters/wehoop.py` | `wehoop` adapter |
| `utils/adapters/balldontlie.py` | REST fallback |
| `utils/adapters/basketball_reference.py` | Historical scraper |
| `utils/adapters/odds_api.py` | Odds adapter |
| `scripts/bootstrap_reference_data.py` | Team/player identity seed |
| `scripts/normalize_raw_data.py` | Raw-to-canonical conversion |
| `scripts/validate_data.py` | Quality checks |
| `scripts/build_features.py` | Feature build independent of fetch |
| `scripts/backtest.py` | Walk-forward model evaluation |
| `scripts/publish_data_health.py` | Health report |
| `pages/7_Data_Health.py` | Operational visibility |
| `tests/contract/` | Source schema contracts |
| `tests/regression/` | Historical edge cases |
| `docs/data_dictionary.md` | Canonical columns |
| `docs/operations.md` | Daily workflow and recovery |
| `docs/model_card.md` | Promoted model documentation |

---

## Refactor Priorities

### Highest priority

1. Artifact isolation
2. League configuration
3. Canonical IDs
4. Canonical data contracts
5. Source adapter boundary
6. Leakage-safe features
7. Chronological evaluation

### Medium priority

1. Data Health UI
2. Raw payload retention
3. Source disagreement reports
4. Versioned prediction snapshots
5. Travel and schedule compression

### Defer

1. Pick 6/player props
2. Referee effects
3. advanced lineup models
4. shared NBA/WNBA package
5. live in-game prediction
