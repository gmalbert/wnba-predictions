# WNBA Predictions Port — Implementation Checklist and Milestones

## Status Legend

```text
[ ] Not started
[~] In progress
[x] Complete
[!] Blocked
```

---

## Milestone 0 — Repository and Safety Isolation

- [ ] Create `gmalbert/wnba-predictions`
- [ ] Copy only required NBA repository history/files
- [ ] Replace NBA branding
- [ ] Add `league_key = "wnba"`
- [ ] Add `stats_league_id = "10"`
- [ ] Add calendar-year season handling
- [ ] Add 10-minute-quarter configuration
- [ ] Namespace all caches under WNBA
- [ ] Namespace all model artifacts under WNBA
- [ ] Add runtime assertion rejecting NBA artifacts
- [ ] Remove committed NBA historical parquet from WNBA repo
- [ ] Add `.env.example`
- [ ] Add source and model version metadata
- [ ] Confirm Streamlit app boots with no external fetches

Exit gate:

- [ ] App starts
- [ ] No NBA model can load
- [ ] No NBA team appears
- [ ] Unit tests pass for league configuration

---

## Milestone 1 — Canonical Reference Data

### Teams

- [ ] Build WNBA teams reference table
- [ ] Add WNBA Stats team IDs
- [ ] Add ESPN team IDs
- [ ] Add BALLDONTLIE team IDs
- [ ] Add abbreviations
- [ ] Add franchise continuity fields
- [ ] Add venue and coordinates
- [ ] Add active season ranges
- [ ] Add conference
- [ ] Test current and historical names

### Players

- [ ] Build canonical player identity table
- [ ] Add source aliases
- [ ] Add team history
- [ ] Add active dates
- [ ] Add normalized names
- [ ] Handle punctuation and suffixes
- [ ] Handle traded players
- [ ] Handle duplicate names

Exit gate:

- [ ] All current teams map across primary sources
- [ ] At least 99% of historical player rows map
- [ ] Unmatched identities are reported, not silently dropped

---

## Milestone 2 — Source Adapters

### WNBA Stats

- [ ] Implement schedule
- [ ] Implement league game logs
- [ ] Implement team game logs
- [ ] Implement player game logs
- [ ] Implement traditional box scores
- [ ] Implement advanced box scores
- [ ] Implement standings
- [ ] Implement rosters
- [ ] Validate playoff data
- [ ] Validate historical depth
- [ ] Add retry, timeout, and cache
- [ ] Add contract fixtures

### ESPN

- [ ] Implement scoreboard
- [ ] Implement schedule
- [ ] Implement event summaries
- [ ] Implement rosters
- [ ] Implement injuries
- [ ] Implement officials
- [ ] Implement venues
- [ ] Implement live status
- [ ] Preserve raw payloads
- [ ] Add schema monitoring

### `wehoop`

- [ ] Implement historical schedule ingestion
- [ ] Implement team box-score ingestion
- [ ] Implement player box-score ingestion
- [ ] Implement play-by-play ingestion
- [ ] Implement officials ingestion
- [ ] Validate quarter length
- [ ] Validate overtime
- [ ] Validate postseason
- [ ] Record release/version metadata

### Odds

- [ ] Add WNBA sport key
- [ ] Normalize team names
- [ ] Implement game matching
- [ ] Store snapshots
- [ ] Handle missing books
- [ ] Handle missing markets
- [ ] Validate spread orientation
- [ ] Add quota telemetry

Exit gate:

- [ ] At least two sources agree on schedule and results
- [ ] Raw responses retained
- [ ] Adapter contract tests pass
- [ ] Failures do not overwrite good data

---

## Milestone 3 — Historical Backfill

- [ ] Select initial historical start season
- [ ] Fetch regular seasons
- [ ] Fetch playoffs
- [ ] Normalize games
- [ ] Normalize team game stats
- [ ] Normalize player game stats
- [ ] Normalize rosters
- [ ] Normalize officials
- [ ] Normalize play-by-play where available
- [ ] Deduplicate games
- [ ] Reconcile scores
- [ ] Verify two team rows per completed game
- [ ] Verify player/team totals
- [ ] Create data dictionary
- [ ] Generate source completeness report

Exit gate:

- [ ] Historical rebuild is repeatable
- [ ] Missing-game rate documented
- [ ] Duplicate rate below threshold
- [ ] All known anomalies documented

---

## Milestone 4 — Feature Engine Port

### Core team features

- [ ] Rolling points scored
- [ ] Rolling points allowed
- [ ] Offensive rating
- [ ] Defensive rating
- [ ] Net rating
- [ ] Pace
- [ ] Effective field-goal percentage
- [ ] Turnover rate
- [ ] Offensive rebound rate
- [ ] Free-throw rate
- [ ] Home/away splits
- [ ] Recent form
- [ ] Opponent-adjusted form
- [ ] Elo
- [ ] Rest days
- [ ] Back-to-back
- [ ] Schedule compression

### WNBA-specific features

- [ ] Travel distance
- [ ] Time-zone change
- [ ] Road-trip length
- [ ] Homestand length
- [ ] Commissioner's Cup
- [ ] Neutral-site game
- [ ] Expansion-team indicator
- [ ] Playoff urgency
- [ ] Lineup continuity
- [ ] Active roster size
- [ ] Unavailable minutes share
- [ ] Unavailable usage share

### Audit

- [ ] Remove per-48 assumptions
- [ ] Add per-40 normalization
- [ ] Remove fixed team-count assumptions
- [ ] Remove NBA division assumptions
- [ ] Remove split-year season assumptions
- [ ] Validate overtime handling
- [ ] Add feature timestamps
- [ ] Add leakage tests

Exit gate:

- [ ] Feature generation deterministic
- [ ] Feature schema versioned
- [ ] No future data in sampled games
- [ ] Baseline feature coverage acceptable

---

## Milestone 5 — Baseline Models

### Models

- [ ] Elo baseline
- [ ] Market-implied baseline
- [ ] Logistic win model
- [ ] Margin regression
- [ ] Total regression
- [ ] Gradient boosting win model
- [ ] Gradient boosting margin model
- [ ] Gradient boosting total model
- [ ] Probability calibration
- [ ] Ensemble evaluation

### Validation

- [ ] Walk-forward split
- [ ] Season-aware folds
- [ ] Log loss
- [ ] Brier score
- [ ] Calibration curve
- [ ] MAE
- [ ] RMSE
- [ ] Residual analysis
- [ ] Market-relative evaluation
- [ ] Confidence-bucket evaluation
- [ ] Feature-importance report
- [ ] Model card

Exit gate:

- [ ] Model beats naive baseline out of sample
- [ ] Calibration is acceptable
- [ ] No leakage
- [ ] Artifacts include WNBA metadata
- [ ] Promotion decision documented

---

## Milestone 6 — Daily Prediction Pipeline

- [ ] Daily schedule fetch
- [ ] Prior-game result refresh
- [ ] Standings refresh
- [ ] Roster refresh
- [ ] Injury refresh
- [ ] Odds refresh
- [ ] Feature build
- [ ] Prediction generation
- [ ] Prediction snapshot storage
- [ ] Data-quality scoring
- [ ] Missing-input handling
- [ ] Postgame grading
- [ ] Performance update
- [ ] GitHub Actions workflows
- [ ] Failure notifications
- [ ] Manual rerun workflow

Exit gate:

- [ ] Pipeline runs automatically
- [ ] Re-running is idempotent
- [ ] Prediction records are versioned
- [ ] Failures are visible
- [ ] Postgame grading reconciles correctly

---

## Milestone 7 — Streamlit Application

### Core pages

- [ ] Game Predictions
- [ ] Team Stats
- [ ] Player Stats
- [ ] Model Performance
- [ ] Data Health

### Prediction display

- [ ] Win probability
- [ ] Predicted margin
- [ ] Predicted total
- [ ] Market line
- [ ] Model edge
- [ ] Confidence
- [ ] Injury freshness
- [ ] Odds timestamp
- [ ] Model version
- [ ] Prediction timestamp

### Safety and transparency

- [ ] No-bet state
- [ ] Missing-data state
- [ ] Stale-data warning
- [ ] Model disagreement warning
- [ ] Source-health indicator
- [ ] Methodology page
- [ ] Limitations page

Exit gate:

- [ ] App works when one optional source is unavailable
- [ ] Users can identify data freshness
- [ ] Predictions match stored records
- [ ] Mobile layout reviewed

---

## Milestone 8 — Injury and Availability Modeling

- [ ] Historical injury-status storage
- [ ] Status normalization
- [ ] Snapshot expiration
- [ ] Starter inference
- [ ] Expected minutes
- [ ] Replacement quality
- [ ] Star absence
- [ ] Team depth
- [ ] Active roster size
- [ ] Manual override interface
- [ ] Audit trail
- [ ] Out-of-sample evaluation

Exit gate:

- [ ] Injury features improve model or are disabled
- [ ] Stale injuries cannot silently persist
- [ ] Manual changes are attributable
- [ ] Prediction changes can be explained

---

## Milestone 9 — Advanced Enrichment

- [ ] Play-by-play possessions
- [ ] Lineup combinations
- [ ] On/off metrics
- [ ] Garbage-time filtering
- [ ] Clutch metrics
- [ ] Shot-location features
- [ ] Transition estimates
- [ ] Half-court estimates
- [ ] Referee collection
- [ ] Referee shrinkage model
- [ ] Travel model
- [ ] Schedule-fatigue model
- [ ] Feature ablation tests

Exit gate:

- [ ] Every enrichment group shows measurable lift
- [ ] Missing enrichment never blocks baseline prediction
- [ ] Small-sample features are regularized

---

## Milestone 10 — Player Props

- [ ] Historical player lines
- [ ] Prop-market normalization
- [ ] Player-game matching
- [ ] Expected minutes
- [ ] Usage projection
- [ ] Distributional models
- [ ] Points
- [ ] Rebounds
- [ ] Assists
- [ ] Three-pointers
- [ ] PRA
- [ ] Fantasy score
- [ ] Over/under probabilities
- [ ] Fair lines
- [ ] Edge thresholds
- [ ] Calibration by prop
- [ ] Injury cutoff controls
- [ ] Line-movement tracking

Exit gate:

- [ ] Historical market data sufficient
- [ ] Prop probabilities calibrated
- [ ] Expected-minutes errors monitored
- [ ] No recommendation without adequate confidence

---

## Milestone 11 — Shared Core Extraction

Proceed only after both NBA and WNBA repositories are stable.

- [ ] Identify truly common modules
- [ ] Extract canonical interfaces
- [ ] Keep league adapters separate
- [ ] Add NBA/WNBA contract tests
- [ ] Preserve independent model artifacts
- [ ] Preserve independent release cadence
- [ ] Document migration
- [ ] Avoid breaking existing NBA deployment

Exit gate:

- [ ] Both apps pass regression tests
- [ ] Shared package reduces duplication without hiding league differences
- [ ] Rollback path exists

---

## Required Documentation

- [ ] Architecture
- [ ] Data sources
- [ ] Endpoint audit
- [ ] Data dictionary
- [ ] Model card
- [ ] Feature definitions
- [ ] Operations runbook
- [ ] Failure recovery
- [ ] Backfill procedure
- [ ] Manual override procedure
- [ ] Deployment instructions
- [ ] Source terms/risk notes
- [ ] Known limitations
- [ ] Release notes

---

## Recommended First Build Order

```text
1. Repository isolation
2. League configuration
3. Team/player identity
4. Schedule and results
5. Team box scores
6. Historical normalization
7. Core team features
8. Baseline models
9. Odds integration
10. Daily predictions
11. Data health
12. Injuries
13. PBP enrichment
14. Player props
15. Shared core extraction
```

---

## Immediate Next Actions

- [ ] Create the WNBA repository from the NBA codebase
- [ ] Add `config/league.toml`
- [ ] Replace hardcoded season constants
- [ ] Replace hardcoded `league_id="00"`
- [ ] Build source endpoint audit script
- [ ] Validate scoreboard and league game log for one WNBA season
- [ ] Build WNBA team identity table
- [ ] Ingest one historical season end-to-end
- [ ] Run the first leakage-safe baseline backtest
