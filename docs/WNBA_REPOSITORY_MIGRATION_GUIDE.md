# WNBA Predictions — Repository-Specific Transition and Migration Guide

## Scope

This document describes how to transition the existing repository:

```text
gmalbert/nba-predictions
```

into a separate WNBA repository:

```text
gmalbert/wnba-predictions
```

It is designed as an execution manual. It explains:

- what to copy;
- what to delete;
- what to preserve unchanged;
- what to refactor before adapting;
- what must be rewritten;
- the order in which changes should be committed;
- how to validate each transition;
- where rollback points should be placed;
- how to avoid contaminating WNBA data or models with NBA artifacts.

The recommended strategy is a **controlled fork followed by progressive replacement of NBA-specific layers**. Do not begin by changing every occurrence of `NBA` to `WNBA`. That would create a repository that appears converted while retaining hidden NBA assumptions.

---

# 1. Transition Strategy

## Recommended approach: independent repository first

Create a new repository from the current NBA codebase, then remove or isolate NBA-specific assets.

Reasons:

1. The NBA application should remain stable.
2. WNBA endpoint behavior must be validated experimentally.
3. WNBA models require separate training data.
4. The two applications will initially have different operational schedules.
5. Shared abstractions are easier to identify after both implementations work.
6. A premature monorepo refactor would combine migration risk with architecture risk.

Do not modify the NBA production repository to support both leagues during the initial WNBA build.

---

# 2. Repository Creation Options

## Option A — GitHub template-style copy

Best when you do not need the full NBA commit history in the new repository.

```bash
git clone https://github.com/gmalbert/nba-predictions.git wnba-predictions
cd wnba-predictions
rm -rf .git
git init
git branch -M main
git add .
git commit -m "chore: initialize WNBA predictions from NBA application structure"
git remote add origin git@github.com:gmalbert/wnba-predictions.git
git push -u origin main
```

Advantages:

- clean WNBA history;
- avoids years of unrelated NBA commits;
- simple mental model.

Disadvantage:

- `git blame` does not point back through NBA history.

## Option B — fork preserving history

Best when preserving provenance and history matters.

```bash
git clone https://github.com/gmalbert/nba-predictions.git wnba-predictions
cd wnba-predictions
git remote rename origin upstream-nba
git remote add origin git@github.com:gmalbert/wnba-predictions.git
git push -u origin main
```

Advantages:

- retains commit history;
- easy to inspect the origin of reused code.

Disadvantages:

- old NBA history may confuse future contributors;
- accidental merges from NBA are possible.

## Recommendation

Use **Option A** unless there is a strong reason to retain NBA history. Add the NBA repository as a read-only reference remote later:

```bash
git remote add nba-reference https://github.com/gmalbert/nba-predictions.git
```

Do not routinely merge from it.

---

# 3. Baseline Snapshot Before Changes

Before deleting or changing anything:

```bash
git tag nba-source-baseline
git branch archive/nba-source-baseline
```

Record:

- source repository URL;
- source commit SHA;
- date copied;
- Python version;
- package lock or requirements state;
- current Streamlit entry point;
- current model artifact names;
- current data directory structure.

Create:

```text
docs/NBA_SOURCE_BASELINE.md
```

Example:

```markdown
# NBA Source Baseline

- Repository: gmalbert/nba-predictions
- Source commit: <SHA>
- Copied: <DATE>
- Purpose: structural starting point for WNBA application
- Policy: no NBA data or model artifacts may be used by WNBA production code
```

This makes later comparisons possible.

---

# 4. First-Pass Inventory

The current repository includes these important areas:

```text
.github/workflows/
config/
data_files/
docs/
models/
pages/
scripts/
utils/
predictions.py
footer.py
requirements.txt
```

Key Python modules include:

```text
utils/data_fetcher.py
utils/feature_engine.py
utils/hoopr_fetcher.py
utils/model_utils.py
utils/prediction_engine.py

scripts/daily_update.py
scripts/fetch_historical.py
scripts/fetch_historical_odds.py
scripts/fetch_hoopr_data.py
scripts/preload_cache.py
scripts/scrape_external.py
scripts/train_models.py
scripts/export_best_bets.py
```

Streamlit pages include:

```text
pages/1_Game_Predictions.py
pages/2_Pick_6.py
pages/3_Standings.py
pages/4_Team_Stats.py
pages/5_Player_Stats.py
pages/6_Model_Performance.py
```

Workflows include:

```text
.github/workflows/nightly-pipeline.yml
.github/workflows/hoopr-daily.yml
.github/workflows/odds-backfill.yml
.github/workflows/odds-snapshot.yml
.github/workflows/referee-assignments.yml
```

---

# 5. Immediate Quarantine of NBA Artifacts

Before changing code, move all NBA-generated assets out of active paths.

## Remove or quarantine

```text
data_files/historical/league_gamelog_*.parquet
data_files/historical/league_playerstats_*.parquet
data_files/historical/league_teamstats_*.parquet
data_files/historical/teamlog_*.parquet
data_files/historical/playerlog_*.parquet
data_files/historical/bst_*.parquet
data_files/historical/bsa_*.parquet
data_files/hoopr/
data_files/best_bets_today.json
models/*
```

Recommended local command:

```bash
mkdir -p archive/nba_data
mkdir -p archive/nba_models

git mv data_files/historical/*.parquet archive/nba_data/ 2>/dev/null || true
git mv models/* archive/nba_models/ 2>/dev/null || true
```

Better for the WNBA repository: delete them entirely and retain them only in the NBA repository.

## Add artifact identity guards

Every saved model should include metadata:

```python
{
    "league_key": "wnba",
    "season_start": 2017,
    "season_end": 2026,
    "feature_schema_version": "...",
    "trained_at": "...",
    "source_commit": "...",
}
```

Every model load must validate:

```python
if metadata["league_key"] != LEAGUE_CONFIG.league_key:
    raise ValueError("Model artifact league mismatch")
```

Every normalized dataset should include a `league_key` column or be stored in a league-specific directory.

---

# 6. Create Configuration Before Rewriting Code

Do this before touching API calls.

## New file: `config/league.toml`

```toml
league_key = "wnba"
display_name = "WNBA"
stats_league_id = "10"
season_format = "calendar_year"
period_minutes = 10
regulation_periods = 4
regulation_minutes = 40
timezone = "America/New_York"
default_season_type = "Regular Season"
```

## New file: `utils/league_config.py`

Responsibilities:

- parse `league.toml`;
- expose typed constants;
- validate supported values;
- format seasons;
- return storage namespaces;
- reject impossible combinations.

Suggested interface:

```python
@dataclass(frozen=True)
class LeagueConfig:
    league_key: str
    display_name: str
    stats_league_id: str
    season_format: str
    period_minutes: int
    regulation_periods: int
    timezone: str

    @property
    def regulation_minutes(self) -> int:
        return self.period_minutes * self.regulation_periods

    def normalize_season(self, value: int | str) -> str:
        ...
```

## Required tests

```text
test_wnba_league_id_is_10
test_wnba_season_2026_remains_2026
test_regulation_minutes_is_40
test_nba_split_year_string_is_rejected_in_wnba_mode
```

Rollback point:

```text
Tag: wnba-migration-config-complete
```

---

# 7. Introduce Canonical Data Contracts

The current code uses raw NBA Stats field names such as:

```text
GAME_ID
TEAM_ID
TEAM_ABBREVIATION
GAME_DATE
MATCHUP
WL
PTS
```

These are useful but should no longer be the contract between every component.

Create:

```text
utils/data_contracts.py
```

## Canonical games schema

```text
league_key
season
season_type
canonical_game_id
source_game_id
game_date
scheduled_start
home_team_id
away_team_id
home_score
away_score
status
neutral_site
overtime_periods
source
retrieved_at
```

## Canonical team-game schema

```text
canonical_game_id
canonical_team_id
opponent_team_id
is_home
game_date
season
season_type
win
points
field_goals_made
field_goals_attempted
three_points_made
three_points_attempted
free_throws_made
free_throws_attempted
offensive_rebounds
defensive_rebounds
assists
turnovers
steals
blocks
personal_fouls
minutes
possessions
source
retrieved_at
```

## Canonical player-game schema

```text
canonical_game_id
canonical_player_id
canonical_team_id
started
minutes
points
rebounds
assists
steals
blocks
turnovers
field_goals_made
field_goals_attempted
three_points_made
three_points_attempted
free_throws_made
free_throws_attempted
source
retrieved_at
```

## Why this step comes early

The existing feature engine has direct source coupling:

- NBA field names;
- hoopR column names;
- abbreviation joins;
- ESPN IDs that cannot directly join to NBA Stats IDs.

The WNBA port should correct this by mapping all sources into canonical IDs before feature computation.

---

# 8. Build Identity Mapping Before Historical Ingestion

Create:

```text
data_files/reference/teams.parquet
data_files/reference/players.parquet
data_files/reference/team_aliases.parquet
data_files/reference/player_aliases.parquet
```

## Team identity fields

```text
canonical_team_id
canonical_franchise_id
display_name
city
nickname
abbreviation
conference
active_from
active_to
venue
latitude
longitude
wnba_stats_team_id
espn_team_id
balldontlie_team_id
basketball_reference_slug
wehoop_team_id
```

## Player identity fields

```text
canonical_player_id
display_name
normalized_name
birth_date
active_from
active_to
wnba_stats_player_id
espn_player_id
balldontlie_player_id
basketball_reference_slug
```

## Matching policy

Use identifiers where available.

Name matching may be used only as a controlled fallback and should emit:

```text
match_method
match_confidence
review_required
```

Do not drop unmatched players. Put them into:

```text
data_files/data_health/unmatched_players.parquet
```

---

# 9. File-by-File Migration Matrix

## Root files

### `predictions.py`

Classification: **retain structure, refactor imports and branding**

Likely responsibilities:

- Streamlit application entry;
- navigation;
- page configuration;
- shared styling;
- summary output.

Actions:

1. Replace NBA title and copy.
2. Move league constants to `league_config.py`.
3. Remove direct data-source references.
4. Ensure all paths use a WNBA namespace.
5. Display model version and source freshness.
6. Add an application startup assertion:

```python
assert LEAGUE_CONFIG.league_key == "wnba"
```

7. Do not preload NBA model files.

Acceptance tests:

- title displays WNBA;
- no NBA teams in UI;
- no NBA path referenced;
- app starts with empty WNBA data.

### `footer.py`

Classification: **reuse with branding review**

Actions:

- replace NBA-specific text;
- review disclaimers;
- add methodology/data freshness links;
- maintain responsible betting language.

### `requirements.txt`

Classification: **audit and update**

Actions:

- retain modeling and Streamlit dependencies;
- verify `nba_api` version can support needed WNBA calls;
- add a schema validation library if desired;
- add testing dependencies;
- remove packages used only by abandoned NBA scrapers;
- consider `pydantic`, `pandera`, or `pyarrow`;
- pin versions for reproducibility.

Do not remove `nba_api` solely because the target is WNBA; the package may still be used as a wrapper around Stats endpoints.

---

## Configuration

### `config/seasons.toml`

Classification: **rewrite**

Current NBA split seasons must be replaced with calendar years.

Suggested:

```toml
historical_start = 2017
current_season = 2026
regular_season_label = "Regular Season"
playoff_label = "Playoffs"

[backfill]
seasons = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
```

Add exceptional-season metadata rather than hardcoding anomalies:

```toml
[season_overrides.2020]
notes = "Pandemic-affected season"
```

---

## Data fetch layer

### `utils/data_fetcher.py`

Classification: **major rewrite**

The current file imports NBA Stats endpoints directly, uses static NBA team/player helpers, hardcodes `league_id="00"`, assumes split-year seasons, and writes NBA-named parquet files.

Do not convert it by editing each function inline. Replace it with a façade over adapters.

New layout:

```text
utils/
├── data_fetcher.py
└── adapters/
    ├── base.py
    ├── wnba_stats.py
    ├── espn.py
    ├── wehoop.py
    └── odds_api.py
```

`data_fetcher.py` should expose application-level methods:

```python
def get_schedule(...)
def get_team_game_stats(...)
def get_player_game_stats(...)
def get_standings(...)
def get_rosters(...)
def get_injuries(...)
def get_officials(...)
```

It should not know endpoint-specific response structures.

#### Function migration approach

For each existing function:

1. Identify the canonical capability.
2. Move raw endpoint code into an adapter.
3. Normalize the response.
4. Add contract validation.
5. Store raw and normalized versions.
6. Add fallback selection.
7. Preserve caching behavior.
8. Replace silent empty-frame errors with structured errors.

#### Specific replacements

Current:

```python
scoreboardv3.ScoreboardV3(game_date=..., league_id="00")
```

New:

```python
stats_adapter.fetch_scoreboard(
    game_date=...,
    league_id=LEAGUE_CONFIG.stats_league_id,
)
```

Current static helpers:

```python
nba_api.stats.static.teams
nba_api.stats.static.players
```

New:

```python
identity_repository.get_teams()
identity_repository.get_players()
```

#### Error policy

The current file catches broad exceptions and often returns empty frames. In the new repository:

- source adapter may return a typed source failure;
- orchestrator may use a fallback;
- UI receives a data-quality state;
- empty data is not treated as successful data.

Suggested exceptions:

```python
class SourceUnavailableError(Exception): ...
class SchemaMismatchError(Exception): ...
class DataIncompleteError(Exception): ...
class IdentityMappingError(Exception): ...
```

---

## Feature layer

### `utils/feature_engine.py`

Classification: **retain core algorithms, refactor source coupling**

The existing file correctly emphasizes shifted rolling and expanding features to avoid leakage. Preserve that principle.

Retain with minor changes:

- `compute_rest_days`;
- `compute_back_to_back`;
- `compute_streak`;
- `add_rolling_features`;
- `add_season_averages`;
- `compute_win_pct`;
- most matchup differential calculations.

Audit or change:

- `parse_is_home` currently parses `"vs."` and `"@"` from `MATCHUP`;
- use canonical `is_home` instead;
- rest-day default and cap;
- `IS_3IN4` definition;
- default rolling windows;
- all NBA uppercase raw-column assumptions;
- any 48-minute/per-48 features;
- fixed minimum-game assumptions.

Replace source-specific constants:

```python
HOOPR_TEAM_STAT_COLS
HOOPR_PBP_STAT_COLS
```

with canonical feature groups:

```python
TEAM_BOX_ENRICHMENT_COLUMNS
PBP_DERIVED_COLUMNS
```

Replace:

```python
enrich_team_game_log_with_hoopr(...)
```

with:

```python
enrich_team_game_log(...)
```

where the joined frame is already canonical.

#### Critical migration fix

The current feature engine joins some enrichment by game date and normalized team abbreviation because source IDs differ.

For WNBA:

- map source IDs to canonical IDs before joining;
- join by `canonical_game_id` and `canonical_team_id`;
- use date/abbreviation only as a reconciliation fallback;
- log fallback matches;
- never silently select one of multiple matches.

#### Leakage validation

Keep `.shift(1)` and add tests that demonstrate it.

Test fixture:

```text
Game 1: 80 points
Game 2: 90 points
Game 3: 100 points
```

The rolling feature for Game 3 must use Games 1 and 2 only.

---

## Enrichment layer

### `utils/hoopr_fetcher.py`

Classification: **replace**

Create:

```text
utils/adapters/wehoop.py
```

Do not simply rename imports. Validate actual WNBA data schemas.

Responsibilities:

- download current and historical WNBA datasets;
- preserve release metadata;
- normalize game/team/player IDs;
- derive source freshness;
- handle historical file organization;
- verify 10-minute quarter behavior;
- expose PBP and box-score capabilities.

### `scripts/fetch_hoopr_data.py`

Classification: **replace**

Create:

```text
scripts/fetch_wehoop_data.py
```

Pipeline:

```text
discover releases
→ download raw files
→ verify checksums/schema
→ store raw
→ normalize IDs
→ aggregate PBP features
→ validate team totals
→ publish normalized parquet
```

Do not commit source downloads blindly. Add file-size and schema checks before replacing existing good data.

---

## Model layer

### `utils/model_utils.py`

Classification: **high reuse**

Actions:

- add league metadata;
- add feature schema hash;
- add training data fingerprint;
- make artifacts league-namespaced;
- ensure deterministic feature ordering;
- add calibration metadata;
- reject incompatible artifacts.

Suggested path:

```text
data_files/model_artifacts/wnba/2026/<model_name>/<version>/
```

### `utils/prediction_engine.py`

Classification: **high reuse with canonical-input migration**

Actions:

- replace raw source fields with canonical feature vectors;
- include data-quality score;
- add abstention states;
- support missing market data;
- support multiple prediction snapshots;
- log model and feature versions.

Possible prediction status values:

```text
ready
insufficient_history
stale_injury_data
missing_odds
identity_error
source_disagreement
model_unavailable
```

### `scripts/train_models.py`

Classification: **reuse orchestration, replace datasets and splits**

Actions:

- load only canonical WNBA features;
- chronological train/test split;
- season-aware folds;
- model metadata;
- baseline comparisons;
- calibration;
- betting metrics;
- feature ablation;
- save model card.

Do not use a random game split as the primary validation.

---

## Historical scripts

### `scripts/fetch_historical.py`

Classification: **rewrite endpoint logic, preserve orchestration pattern**

New stages:

```text
fetch raw source data
→ validate source response
→ normalize
→ resolve identity
→ deduplicate
→ reconcile sources
→ save partitioned data
→ produce completeness report
```

Recommended partitions:

```text
data_files/normalized/team_game_stats/season=2024/
data_files/normalized/player_game_stats/season=2024/
```

### `scripts/scrape_external.py`

Classification: **decompose**

A large multi-source scraper is difficult to test and migrate.

Split into:

```text
utils/adapters/basketball_reference.py
utils/adapters/espn.py
utils/adapters/official_reports.py
utils/adapters/odds_api.py
```

Keep source parsing separate.

Delete scrapers that no longer have a defined role.

### `scripts/fetch_historical_odds.py`

Classification: **reuse framework, replace sport and mapping logic**

Actions:

- WNBA sport key;
- canonical team mapping;
- calendar seasons;
- rescheduled game handling;
- snapshot provenance;
- no forced match on ambiguous games.

### `scripts/daily_update.py`

Classification: **reuse orchestration after source refactor**

Recommended order:

```text
1. Fetch schedule
2. Reconcile game identities
3. Fetch completed game results
4. Fetch rosters
5. Fetch injuries
6. Fetch odds
7. Normalize
8. Validate
9. Build features
10. Generate predictions
11. Publish health report
```

### `scripts/preload_cache.py`

Classification: **reuse concept, make capability-aware**

Do not allow cache warming to fail because optional PBP or injury data is unavailable.

Separate:

```text
required caches
optional enrichment caches
UI caches
```

### `scripts/export_best_bets.py`

Classification: **defer**

Initially disable recommendations while the WNBA model is unvalidated.

When re-enabled:

- require minimum edge;
- require data-confidence threshold;
- require recent odds;
- require acceptable calibration;
- allow `no bet`.

---

## Streamlit pages

### `pages/1_Game_Predictions.py`

Classification: **retain layout concepts, refactor data dependencies**

Actions:

- use prediction records instead of rebuilding raw features inside page;
- show source freshness;
- show odds timestamp;
- show injury timestamp;
- show prediction stage;
- show model version;
- show no-bet or insufficient-data status;
- WNBA branding and team assets.

Avoid direct source calls in rendering code.

### `pages/2_Pick_6.py`

Classification: **disable initially**

Player props should not be included in Phase 1.

Options:

1. remove page temporarily;
2. retain a development-only placeholder;
3. hide behind a feature flag.

Recommended:

```toml
[features]
player_props = false
```

Do not show NBA player names or stale NBA artifacts.

### `pages/3_Standings.py`

Classification: **moderate adaptation**

Actions:

- handle WNBA standings schema;
- avoid NBA division assumptions;
- make conference display dynamic;
- support overall playoff seeding rules as applicable;
- source from canonical standings.

### `pages/4_Team_Stats.py`

Classification: **high reuse**

Actions:

- use per-40 metrics where player-minute normalization appears;
- dynamic team list;
- WNBA league averages;
- update labels;
- display sample size;
- use canonical data.

### `pages/5_Player_Stats.py`

Classification: **moderate adaptation**

Actions:

- canonical player identity;
- calendar season selector;
- dynamic roster;
- per-40 rather than per-48 options;
- handle shorter season and smaller samples;
- expose games/minutes thresholds.

### `pages/6_Model_Performance.py`

Classification: **high reuse**

Actions:

- clear all NBA performance history;
- WNBA-only metrics;
- add market baseline;
- calibration;
- walk-forward results;
- performance by prediction stage;
- performance by confidence and source-health bucket.

### New page: `pages/7_Data_Health.py`

Display:

- source freshness;
- endpoint status;
- game completeness;
- unmapped teams/players;
- odds matching failures;
- injury freshness;
- current model artifact;
- current schema version;
- last successful workflow.

---

## Workflows

### `nightly-pipeline.yml`

Classification: **reuse structure, rewrite schedule and steps**

WNBA season timing differs from NBA.

Actions:

- run only relevant months or allow manual/offseason mode;
- fetch WNBA sources;
- validate before committing;
- separate required and optional steps;
- upload logs/artifacts on failure;
- prevent partial data replacement.

### `hoopr-daily.yml`

Classification: **replace**

New:

```text
wehoop-daily.yml
```

### `odds-snapshot.yml`

Classification: **reuse with WNBA sport key and cadence**

WNBA prop and game markets may appear later or vary by book. Add market-availability logging.

### `odds-backfill.yml`

Classification: **reuse with WNBA date ranges**

### `referee-assignments.yml`

Classification: **disable or replace with collection-only workflow**

Do not feed referee features to models initially.

New workflow:

```text
officials-collection.yml
```

It should collect and normalize data without altering predictions.

---

# 10. New Adapter Architecture

## Base protocol

```python
from typing import Protocol
import pandas as pd

class BasketballDataAdapter(Protocol):
    source_name: str

    def fetch_schedule(self, date_from, date_to) -> pd.DataFrame:
        ...

    def fetch_team_game_stats(self, season: int) -> pd.DataFrame:
        ...

    def fetch_player_game_stats(self, season: int) -> pd.DataFrame:
        ...
```

## Source registry

```python
SOURCE_PRIORITY = {
    "schedule": ["wnba_stats", "espn", "balldontlie"],
    "team_game_stats": ["wnba_stats", "wehoop", "basketball_reference"],
    "player_game_stats": ["wnba_stats", "wehoop", "basketball_reference"],
    "injuries": ["espn", "manual_override"],
    "odds": ["the_odds_api"],
}
```

## Important rule

Fallbacks should not merge arbitrary values field-by-field without provenance.

Choose one of:

- primary record;
- secondary record;
- reconciled record with explicit resolution rule.

Retain source values for comparison.

---

# 11. Commit-by-Commit Migration Sequence

## Commit 1 — establish WNBA repository

```text
chore: initialize WNBA predictions repository from NBA structure
```

Changes:

- create repository;
- record source SHA;
- no functional changes.

Rollback: reset to initial commit.

## Commit 2 — quarantine NBA artifacts

```text
chore: remove NBA data and model artifacts
```

Changes:

- remove NBA parquet;
- remove NBA models;
- disable workflows;
- disable player props;
- add artifact guards.

Acceptance:

- app cannot load NBA model;
- repository contains no active NBA generated data.

## Commit 3 — add WNBA league configuration

```text
feat: add WNBA league configuration and season handling
```

Changes:

- `league.toml`;
- typed config;
- calendar seasons;
- 10-minute quarters;
- path namespace.

Acceptance:

- config tests pass.

## Commit 4 — add canonical data contracts

```text
feat: define canonical game, team, player, injury, and odds schemas
```

Changes:

- schema definitions;
- validators;
- test fixtures.

Acceptance:

- invalid schemas fail clearly.

## Commit 5 — add identity layer

```text
feat: add canonical WNBA team and player identity mapping
```

Changes:

- team reference;
- player reference;
- aliases;
- matching reports.

Acceptance:

- current teams map across primary sources.

## Commit 6 — add WNBA Stats schedule adapter

```text
feat: add WNBA Stats schedule and scoreboard adapter
```

Acceptance:

- date range fetch works;
- league ID verified;
- raw payload saved;
- normalized schema validated.

## Commit 7 — add historical team-game ingestion

```text
feat: ingest and normalize WNBA team game logs
```

Acceptance:

- two rows per completed game;
- scores reconcile.

## Commit 8 — port feature engine to canonical data

```text
refactor: migrate feature engine to canonical WNBA schemas
```

Acceptance:

- rolling features use only prior games;
- no abbreviation join required.

## Commit 9 — build baseline training pipeline

```text
feat: train baseline WNBA win, margin, and total models
```

Acceptance:

- chronological backtest;
- artifact metadata;
- baseline reports.

## Commit 10 — add odds integration

```text
feat: add WNBA odds snapshots and game matching
```

Acceptance:

- home/away sign verified;
- unmatched odds retained;
- snapshots timestamped.

## Commit 11 — generate daily predictions

```text
feat: generate versioned daily WNBA predictions
```

Acceptance:

- output includes provenance;
- missing odds does not crash.

## Commit 12 — migrate Streamlit predictions page

```text
feat: add WNBA game predictions interface
```

Acceptance:

- page consumes stored prediction records;
- freshness shown.

## Commit 13 — add ESPN roster and injury adapters

```text
feat: add WNBA roster and injury status ingestion
```

Acceptance:

- status history retained;
- stale statuses expire.

## Commit 14 — add `wehoop` enrichment

```text
feat: add wehoop WNBA box score and play-by-play enrichment
```

Acceptance:

- canonical joins;
- optional failure does not block predictions.

## Commit 15 — add data-health page and workflows

```text
feat: add WNBA source health reporting and automation
```

Acceptance:

- failures visible;
- no corrupt replacement.

## Commit 16 — evaluate advanced features

```text
experiment: evaluate WNBA travel, lineup, PBP, and availability features
```

Do not automatically promote experiments.

## Commit 17 — player props foundation

Only after team model and injury pipeline are stable.

---

# 12. Rollback Strategy

Create tags at major gates:

```text
wnba-v0-repository-isolated
wnba-v1-data-ingestion
wnba-v2-baseline-model
wnba-v3-daily-predictions
wnba-v4-injury-aware
wnba-v5-pbp-enriched
```

For data replacement:

1. write to a temporary path;
2. validate;
3. atomically replace active file;
4. retain previous version;
5. record manifest.

Example:

```text
team_game_stats.parquet.tmp
team_game_stats.parquet
team_game_stats.parquet.previous
```

For models:

- never overwrite the only working model;
- use versioned directories;
- maintain `current.json` pointer;
- rollback by switching pointer.

---

# 13. Acceptance Test Suite

## Repository isolation

- no active NBA team reference;
- no active NBA model;
- no NBA historical parquet;
- no `"league_id='00'"` in WNBA production code;
- no split-year current season.

## Source layer

- schedule available for known date;
- completed game score agrees across sources;
- raw payload archived;
- schema validation active;
- rate limiting bounded.

## Identity

- all current teams map;
- unmapped player report generated;
- duplicate normalized name does not auto-resolve incorrectly.

## Features

- rolling calculations shifted;
- WNBA regulation is 40 minutes;
- travel features use correct venue;
- season resets occur at calendar-year boundary.

## Models

- chronological split;
- artifact league metadata;
- feature schema match;
- calibration output;
- market baseline.

## UI

- WNBA branding;
- source timestamps;
- model timestamp;
- no-bet state;
- missing data state;
- mobile rendering.

## Operations

- workflow rerun is idempotent;
- failure does not replace valid data;
- logs retained;
- model rollback works.

---

# 14. What Not to Do

Do not:

- global-replace `NBA` with `WNBA`;
- reuse NBA models;
- retain NBA parquet in active WNBA paths;
- join different sources only by date and abbreviation when canonical IDs can be used;
- assume every NBA Stats endpoint supports WNBA identically;
- use random train/test split as the main evaluation;
- enable referee effects from small samples;
- publish player props before expected-minutes and injury data are stable;
- silently return an empty frame for every source exception;
- force a prediction when critical inputs are stale;
- combine opening and closing odds without timestamp labels;
- extract a shared NBA/WNBA package before the WNBA application works.

---

# 15. Final Transition Definition

The transition is complete when:

1. the WNBA repository operates independently;
2. all active data is WNBA-specific;
3. all models are trained only on WNBA records;
4. source adapters normalize to canonical contracts;
5. source identity mappings are explicit;
6. feature calculations have no NBA duration or season assumptions;
7. daily predictions are reproducible and versioned;
8. data quality and freshness are visible;
9. the application degrades safely when optional sources fail;
10. the NBA repository has not been destabilized.
