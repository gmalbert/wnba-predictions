# WNBA Predictions Port — Master Plan

## Objective

Port `gmalbert/nba-predictions` into a production-quality WNBA predictions application while preserving the reusable modeling, caching, evaluation, odds, and Streamlit architecture.

The WNBA application should not be implemented as a superficial NBA-to-WNBA rename. It should use:

- shared basketball modeling concepts;
- WNBA-specific data adapters;
- WNBA-specific season and timing rules;
- independently trained models;
- independently validated thresholds;
- resilient fallbacks for thinner data coverage.

Recommended initial repository:

```text
gmalbert/wnba-predictions
```

Recommended long-term architecture:

```text
basketball-predictions/
├── core/
│   ├── caching.py
│   ├── evaluation.py
│   ├── feature_contracts.py
│   ├── model_utils.py
│   ├── odds.py
│   └── prediction_engine.py
└── leagues/
    ├── nba/
    └── wnba/
```

Do not extract a shared package until the WNBA implementation is stable enough to reveal which abstractions are genuinely common.

---

## Executive Assessment

Estimated portability of the existing NBA repository:

| Area | Reuse Estimate | WNBA Action |
|---|---:|---|
| Modeling framework | 85–95% | Reuse structure; retrain all models |
| Evaluation and calibration | 85–95% | Reuse; recalculate thresholds |
| Feature engineering | 65–80% | Audit season, pace, minutes, and roster assumptions |
| Streamlit interface | 70–90% | Rebrand and adapt schemas |
| Caching and parquet storage | 85–95% | Reuse with league-specific namespaces |
| Odds pipeline | 65–85% | Change sport key, mappings, and sparse-market handling |
| NBA Stats acquisition | 35–60% | Add WNBA league parameters and endpoint validation |
| hoopR enrichment | 0–25% | Replace with `wehoop` / WNBA-specific ingestion |
| Injury pipeline | 20–40% | Rebuild around WNBA/ESPN sources |
| Referee pipeline | 10–35% | Rebuild and disable features until validated |
| Existing trained models | 0% | Never reuse NBA fitted models |
| Existing NBA historical data | 0% | Keep fully separate |

---

## Core Design Principles

### 1. Separate league configuration from prediction logic

Create a league configuration object rather than scattering WNBA constants throughout the code.

```python
LEAGUE_CONFIG = {
    "league_key": "wnba",
    "stats_league_id": "10",
    "season_format": "calendar_year",
    "period_minutes": 10,
    "regulation_minutes": 40,
    "timezone": "America/New_York",
    "default_rolling_windows": [3, 5, 10],
}
```

The configuration must control:

- league identifier;
- season parsing;
- regular-season and playoff labels;
- quarter length;
- regulation minutes;
- normalization basis;
- roster size assumptions;
- schedule timezone;
- current season;
- file namespaces;
- API sport keys;
- UI branding.

### 2. Use a canonical data contract

Every source adapter should normalize into stable internal tables.

Core tables:

```text
games
team_game_stats
player_game_stats
teams
players
rosters
injuries
odds_snapshots
officials
play_by_play
lineups
predictions
model_results
```

The prediction engine should consume canonical tables, not raw ESPN, WNBA Stats, or `wehoop` responses.

### 3. Preserve raw data

Use a bronze/silver/gold layout:

```text
data_files/
├── raw/
│   ├── espn/
│   ├── wnba_stats/
│   ├── wehoop/
│   └── odds/
├── normalized/
├── features/
├── predictions/
├── reference/
└── model_artifacts/
```

Raw source payloads are important for:

- schema-change diagnosis;
- replaying parsers;
- provenance;
- regression testing;
- filling historical gaps without repeated scraping.

### 4. Build source fallbacks deliberately

No single free source should be treated as sufficient.

Recommended hierarchy:

| Data Type | Primary | Secondary | Historical/Validation |
|---|---|---|---|
| Schedule/results | WNBA Stats or ESPN | BALLDONTLIE | Basketball Reference |
| Team/player box scores | WNBA Stats | `wehoop` / ESPN | Basketball Reference |
| Play-by-play | `wehoop` / ESPN | WNBA Stats | Basketball Reference or PBPStats |
| Standings | WNBA Stats | ESPN | Basketball Reference |
| Rosters | ESPN / WNBA Stats | BALLDONTLIE | Team sites |
| Injuries | ESPN | official reports/team sources | manual override |
| Odds | The Odds API | ESPN markets | archived snapshots |
| Officials | ESPN event data / `wehoop` | WNBA box scores | canonical history |
| Advanced metrics | derived internally | WNBA Stats | PBPStats / Her Hoop Stats |

### 5. Never silently substitute stale data

Each normalized dataset should include:

```text
source
source_retrieved_at
source_event_updated_at
is_stale
schema_version
parser_version
```

Predictions should display a data-quality warning when critical inputs are stale or missing.

---

## WNBA-Specific Differences That Must Be Modeled

### Season format

NBA:

```text
2025-26
```

WNBA:

```text
2026
```

Do not coerce WNBA seasons into split-year NBA formatting.

### Game duration

WNBA regulation uses four 10-minute quarters.

Audit all formulas involving:

- pace;
- possessions;
- per-minute projections;
- per-40 versus per-48 rates;
- lineup minutes;
- expected player workload;
- live-game clock logic;
- overtime normalization.

### Schedule density and rest

WNBA travel and scheduling require league-specific features:

- days of rest;
- same-day travel impossibility checks;
- one-day-rest frequency;
- back-to-backs;
- three games in five days;
- four games in seven days;
- cross-country travel;
- time-zone change;
- road-trip length;
- homestand length;
- travel distance;
- neutral-site games;
- Commissioner's Cup games;
- playoff series context.

### Roster and player impact

Smaller rosters and concentrated star usage mean injury effects may be nonlinear.

Potential features:

- unavailable minutes share;
- unavailable usage share;
- unavailable win-shares proxy;
- starter absences;
- top-two usage absences;
- replacement player quality;
- lineup continuity;
- active roster size;
- two-way or hardship roster changes, if applicable;
- recent transactions.

### League expansion and franchise continuity

Maintain stable franchise identity separate from displayed team name.

Reference table fields:

```text
canonical_franchise_id
source_team_id
source_name
abbreviation
city
active_from
active_to
predecessor_franchise_id
conference
venue
latitude
longitude
```

This prevents historical discontinuities when names, cities, or source IDs change.

---

## Recommended Repository Structure

```text
wnba-predictions/
├── app.py
├── config/
│   ├── league.toml
│   ├── seasons.toml
│   ├── sources.toml
│   ├── feature_flags.toml
│   └── model_config.toml
├── data_files/
│   ├── raw/
│   ├── normalized/
│   ├── features/
│   ├── historical/
│   ├── predictions/
│   ├── reference/
│   └── model_artifacts/
├── docs/
│   ├── architecture.md
│   ├── data_dictionary.md
│   ├── data_sources.md
│   ├── model_card.md
│   ├── operations.md
│   └── validation.md
├── pages/
│   ├── 1_Game_Predictions.py
│   ├── 2_Player_Props.py
│   ├── 3_Team_Stats.py
│   ├── 4_Player_Stats.py
│   ├── 5_Model_Performance.py
│   └── 6_Data_Health.py
├── scripts/
│   ├── bootstrap_reference_data.py
│   ├── fetch_historical.py
│   ├── fetch_daily.py
│   ├── fetch_wehoop_data.py
│   ├── fetch_odds.py
│   ├── fetch_injuries.py
│   ├── normalize_raw_data.py
│   ├── build_features.py
│   ├── train_models.py
│   ├── backtest.py
│   ├── generate_predictions.py
│   ├── validate_data.py
│   └── publish_data_health.py
├── tests/
│   ├── fixtures/
│   ├── contract/
│   ├── integration/
│   ├── regression/
│   └── unit/
└── utils/
    ├── adapters/
    │   ├── base.py
    │   ├── espn.py
    │   ├── wnba_stats.py
    │   ├── wehoop.py
    │   ├── balldontlie.py
    │   ├── basketball_reference.py
    │   └── odds_api.py
    ├── caching.py
    ├── data_contracts.py
    ├── data_fetcher.py
    ├── feature_engine.py
    ├── identity.py
    ├── model_utils.py
    ├── prediction_engine.py
    ├── quality.py
    └── source_registry.py
```

---

## File-Level Porting Plan

### Reuse with minor modifications

#### `utils/model_utils.py`

Retain:

- estimator creation;
- fit/predict interfaces;
- serialization;
- calibration;
- probability utilities;
- metrics;
- feature importance output.

Change:

- model metadata must include `league_key`;
- artifact paths must include league and season;
- all fitted artifacts must be WNBA-only;
- time-series cross-validation must use WNBA season boundaries.

#### `utils/prediction_engine.py`

Retain:

- prediction orchestration;
- feature assembly pattern;
- edge computation;
- confidence tiering;
- output formatting.

Change:

- consume canonical WNBA features;
- reject NBA model artifacts;
- support missing odds;
- support missing injury inputs;
- expose data-quality status;
- version prediction outputs.

#### `scripts/train_models.py`

Retain:

- training flow;
- holdout evaluation;
- model comparison;
- artifact generation.

Change:

- use chronological validation;
- avoid random game-level train/test splits;
- include expansion-era segmentation where necessary;
- evaluate class calibration and betting metrics separately;
- use season-aware sample weighting.

### Reuse after substantial audit

#### `utils/feature_engine.py`

Audit every feature for:

- NBA-specific season labels;
- 48-minute normalization;
- 12-minute quarter assumptions;
- 30-team assumptions;
- conference and division assumptions;
- fixed roster sizes;
- regular-season game count assumptions;
- playoff format assumptions;
- minimum sample thresholds.

Add WNBA-specific features:

- travel distance;
- schedule compression;
- Commissioner's Cup;
- lineup continuity;
- active-roster depth;
- star-absence burden;
- neutral-site indicator;
- late-season playoff urgency;
- expansion-team indicator;
- compressed-season or unusual-season indicator.

#### Streamlit pages

Reuse page architecture and widgets.

Add:

- source freshness display;
- missing-input warnings;
- WNBA team mapping;
- WNBA logos;
- calendar-year season controls;
- data-health page;
- model version and last trained date;
- explicit distinction between market-implied and model probabilities.

### Replace or rebuild

#### `utils/data_fetcher.py`

Replace direct NBA-specific assumptions with adapters.

Do not let application pages call source-specific endpoints directly.

New interface example:

```python
def get_schedule(date_from, date_to) -> pd.DataFrame: ...
def get_team_game_logs(season) -> pd.DataFrame: ...
def get_player_game_logs(season) -> pd.DataFrame: ...
def get_rosters(season) -> pd.DataFrame: ...
def get_injuries(as_of) -> pd.DataFrame: ...
```

#### `utils/hoopr_fetcher.py`

Replace with `utils/wehoop_fetcher.py` or a generic adapter.

The adapter should ingest:

- schedule;
- play-by-play;
- box scores;
- rosters;
- officials;
- win probability where available.

#### Injury pipeline

Rebuild around:

- ESPN;
- official WNBA/team reports;
- manual overrides;
- timestamped status changes.

Normalize statuses:

```text
available
probable
questionable
doubtful
out
inactive
suspended
unknown
```

#### Referee pipeline

Start as collection-only.

Do not enable referee effects in production predictions until:

- name normalization is stable;
- assignment history is sufficiently complete;
- minimum-game thresholds are met;
- out-of-sample lift is demonstrated.

---

## Data Source Implementation Strategy

### WNBA Stats endpoints

Use WNBA league ID where supported:

```text
league_id = "10"
```

Endpoint validation matrix should record:

```text
endpoint
supports_league_id
required_parameters
earliest_season
latest_validated_season
schema_hash
known_gaps
fallback_source
```

Never assume the Python wrapper exposes every needed parameter. Direct HTTP calls may be preferable for some endpoints.

### `wehoop`

Use as the WNBA counterpart to the NBA repo's `hoopR` enrichment.

Primary uses:

- play-by-play;
- cleaned event data;
- team box scores;
- player box scores;
- officials;
- rosters;
- schedule enrichment.

Preserve source-specific IDs and map them to canonical IDs.

### ESPN

Use for:

- schedule fallback;
- scoreboard;
- event summaries;
- rosters;
- injuries;
- officials;
- broadcasts;
- venue;
- live status;
- possible odds fallback.

Because undocumented ESPN JSON schemas can change, archive raw payloads and maintain parser regression tests.

### BALLDONTLIE

Use as:

- simple REST fallback;
- schedule/results cross-check;
- team/player reference supplement.

Do not make paid-only endpoints a hard dependency for the free baseline.

### Basketball Reference

Use for:

- historical validation;
- franchise-season summaries;
- game logs;
- advanced metrics when reliably available.

Scrapers must use:

- throttling;
- caching;
- identifiable user agent;
- retry limits;
- schema tests;
- HTML fixture tests.

### PBPStats / Her Hoop Stats / Statbunker

Treat as optional enrichment or validation until licensing, access stability, and historical completeness are confirmed.

---

## Modeling Plan

### Initial targets

Build separate models for:

1. Home-team win probability
2. Final margin
3. Game total

Optional later targets:

4. Team total
5. First-half margin
6. First-half total
7. Player props
8. Live win probability

### Baseline models

Start with interpretable baselines:

- Elo;
- logistic regression;
- ridge regression;
- gradient boosting;
- market-only baseline.

Then compare:

- XGBoost;
- LightGBM;
- calibrated ensembles;
- hierarchical or Bayesian approaches for sparse seasons.

### Validation

Use walk-forward validation:

```text
Train: prior seasons
Validate: next season segment
Test: most recent held-out period
```

Required metrics:

#### Win probability

- log loss;
- Brier score;
- ROC AUC;
- calibration error;
- calibration curve;
- accuracy;
- market-relative log loss.

#### Margin and total

- MAE;
- RMSE;
- median absolute error;
- directional accuracy versus spread;
- residual distribution;
- error by rest, travel, and injury buckets.

#### Betting evaluation

- closing-line value;
- ATS win rate;
- totals win rate;
- return on investment;
- maximum drawdown;
- average odds;
- edge-bucket performance;
- confidence calibration;
- bookmaker and market coverage.

Do not promote a model based on raw ATS win rate alone.

### Leakage controls

Features for a game may only use data available before that game's prediction timestamp.

Prohibited leakage examples:

- final injury status published after tipoff;
- closing line used in an opening-line model;
- season averages containing the target game;
- future roster assignments;
- postgame corrections;
- final starting lineup in a pre-lineup model.

Every feature table should include:

```text
feature_as_of
game_start_time
prediction_generated_at
```

---

## Player Props Plan

Defer player props until the team model and player availability pipeline are stable.

Required prerequisites:

- canonical player IDs;
- daily roster snapshots;
- starter inference;
- injury status history;
- expected minutes;
- role and usage features;
- opponent positional or role defense;
- blowout risk;
- rest and travel;
- historical prop lines;
- line movement snapshots.

Models should predict distributions, not only point estimates.

Possible outputs:

```text
mean projection
median projection
standard deviation
probability over
probability under
fair line
market line
edge
data confidence
```

Use separate models or thresholds for:

- points;
- rebounds;
- assists;
- three-pointers;
- points + rebounds + assists;
- fantasy score.

---

## Operational Workflows

### Historical bootstrap

Manual workflow:

```text
fetch raw historical data
→ normalize
→ validate
→ build features
→ train
→ backtest
→ publish model card
```

### Daily pregame workflow

Recommended cadence:

1. Early morning: schedule, rosters, prior results, standings
2. Midday: injuries, odds, team metrics
3. Two hours before games: injuries and odds refresh
4. 30–60 minutes before games: confirmed availability/lineup refresh
5. Postgame: final results and box scores
6. Overnight: feature rebuild, performance scoring, model monitoring

### GitHub Actions

Suggested workflows:

```text
wnba-historical-bootstrap.yml
wnba-daily-refresh.yml
wnba-pregame-refresh.yml
wnba-odds-snapshot.yml
wnba-postgame-results.yml
wnba-weekly-retrain.yml
wnba-data-quality.yml
```

Avoid frequent commits of large generated files when object storage is available. If using GitHub as storage initially, keep artifacts compact and deterministic.

---

## Data Quality Controls

Required checks:

### Schedule

- duplicate games;
- impossible home/away pairing;
- missing start time;
- invalid team IDs;
- game date outside season;
- inconsistent status.

### Team game rows

- exactly two team rows per completed game;
- winner/loser consistency;
- points agreement;
- possession plausibility;
- no duplicate source records.

### Player rows

- player totals reconcile approximately to team totals;
- minutes plausible;
- inactive players not assigned minutes;
- player-team mapping valid.

### Odds

- home/away mapping verified;
- market timestamp before game;
- no inverted spread sign;
- no stale odds mislabeled as current;
- source/bookmaker retained.

### Injuries

- timestamped updates;
- player-team mapping;
- unknown statuses flagged;
- manual override provenance;
- status not carried indefinitely without expiry.

### Model inputs

- no future timestamps;
- no missing team feature vector;
- no NBA artifacts;
- feature schema exactly matches trained model.

---

## Testing Plan

### Unit tests

Test:

- season parsing;
- league config;
- team-name normalization;
- ID mapping;
- possession formulas;
- per-40 normalization;
- odds sign handling;
- injury-status normalization;
- feature cutoff logic.

### Contract tests

For every source adapter:

- expected columns;
- expected types;
- required non-null fields;
- schema hash;
- source response fixture.

### Integration tests

Test complete flows:

```text
source response
→ normalized table
→ features
→ prediction
```

### Regression tests

Store representative fixtures for:

- regular-season game;
- playoff game;
- postponed game;
- overtime game;
- neutral-site game;
- missing odds;
- player traded midseason;
- renamed team;
- source schema change.

### Model tests

- artifact league metadata;
- deterministic feature ordering;
- train/predict schema consistency;
- calibration report generation;
- no leakage in time cutoffs.

---

## Enhancements Beyond the NBA Repo

### 1. Data Health page

Display:

- source status;
- last successful fetch;
- age of each dataset;
- missing games;
- missing odds;
- missing injuries;
- parser errors;
- current model version;
- current feature schema version.

### 2. Prediction provenance

Every prediction record should include:

```text
prediction_id
game_id
model_version
feature_schema_version
generated_at
odds_snapshot_id
injury_snapshot_id
source_freshness_score
```

### 3. Multi-stage predictions

Save separate snapshots:

```text
open
morning
midday
pregame
confirmed_lineup
close
```

This permits:

- line-movement analysis;
- measuring information value;
- identifying when the model performs best;
- distinguishing forecast skill from late market copying.

### 4. Market-relative benchmarking

Every model should be compared against:

- moneyline implied probability;
- spread-derived probability;
- consensus market;
- simple Elo;
- prior-season baseline.

### 5. Uncertainty and abstention

Permit the model to output:

```text
no bet
insufficient data
stale injury data
market unavailable
high model disagreement
```

A prediction application should not force a wager recommendation for every game.

### 6. Source confidence scoring

Compute a confidence score based on:

- freshness;
- source agreement;
- completeness;
- injury certainty;
- odds availability;
- lineup confirmation;
- historical sample size.

### 7. Expansion readiness

Make team count dynamic. Avoid assumptions that the league always has a fixed number of teams.

### 8. Reproducible model cards

For every promoted model, publish:

- training period;
- test period;
- feature list;
- hyperparameters;
- calibration;
- error metrics;
- betting simulation assumptions;
- known limitations;
- source versions.

---

## Release Phases

### Phase 0 — Repository creation and isolation

Deliverables:

- new WNBA repository;
- copied reusable code;
- WNBA branding;
- league configuration;
- separate data/model paths;
- NBA artifact rejection.

Exit criteria:

- application launches;
- no NBA data loads accidentally;
- league configuration is tested.

### Phase 1 — Historical team model

Scope:

- schedule;
- results;
- team box scores;
- rolling features;
- Elo;
- rest;
- baseline win/margin/total models.

Exit criteria:

- at least several historical seasons normalized;
- backtest runs end-to-end;
- no timestamp leakage;
- data checks pass.

### Phase 2 — Daily predictions and odds

Scope:

- daily schedule;
- live data refresh;
- odds snapshots;
- pregame predictions;
- model performance logging.

Exit criteria:

- predictions generated automatically;
- odds matching is verified;
- missing-market behavior is safe;
- model-versus-market reports exist.

### Phase 3 — Advanced team enrichment

Scope:

- play-by-play;
- lineup continuity;
- travel;
- compressed schedule;
- richer advanced metrics.

Exit criteria:

- each added feature group demonstrates out-of-sample value;
- feature failures do not block baseline predictions.

### Phase 4 — Injuries and availability

Scope:

- injury ingestion;
- status history;
- active roster snapshots;
- star-impact and unavailable-minutes features.

Exit criteria:

- injury provenance is visible;
- stale statuses expire safely;
- prediction changes are auditable.

### Phase 5 — Player props

Scope:

- expected minutes;
- player stat distributions;
- prop matching;
- probability and edge outputs.

Exit criteria:

- historical lines available;
- no role/injury leakage;
- calibration acceptable by prop type.

### Phase 6 — Shared basketball core

Only after NBA and WNBA implementations are stable:

- extract common interfaces;
- retain league adapters;
- add cross-league contract tests;
- avoid coupling deployment schedules.

---

## Definition of Done

The WNBA port is production-ready when:

- historical data can be rebuilt from documented sources;
- daily predictions run without manual intervention;
- all artifacts identify league and model version;
- no NBA models or data can load into the WNBA application;
- source failures degrade gracefully;
- model inputs are timestamp-safe;
- predictions are benchmarked against the market;
- calibration and backtests are published;
- odds, injuries, and source freshness are auditable;
- the application can abstain when data quality is insufficient;
- documentation covers operations, data contracts, and recovery procedures.
