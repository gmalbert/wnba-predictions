# 00A — Visual Reference (Streamlit baseline)

> **Purpose.** Page-by-page inventory of the existing Streamlit WNBA
> Predictions design. Captures navigation, layout, colors, and component
> shapes so the React port reproduces them faithfully during the parity
> phase. Section 25 / 32A of the conversion runbook forbid redesign during
> parity, so this document is the visual source of truth.
>
> **Status.** Capture-side: no screenshots have been generated yet. The
> description below is taken from reading every Streamlit page (and its
> injected CSS) at the time of audit. Screenshots are generated during
> Phase 5 (`docs/react-migration/parity/<page>/streamlit-*.png`).

---

## 1. Global chrome

### 1.1 Active theme (at audit time)

`.streamlit/config.toml`:

```toml
[theme]
primaryColor       = "#D6286A"
backgroundColor    = "#120B1C"
secondaryBackgroundColor = "#1D1429"
textColor          = "#F2EBF7"
font               = "sans serif"
```

This is the *nighttime* default (Wine Violet family). `utils.theme_utils` may
swap to a *daytime* theme at runtime based on browser-local time.

### 1.2 WNBA brand colors used inline

| Token | Hex | Where used |
|---|---|---|
| WNBA red | `#C8102E` | Probability-bar "away" half |
| WNBA blue | `#1D428A` | Probability-bar "home" half |
| High confidence | `#16a34a` | Matchup card confidence badge |
| Medium confidence | `#d97706` | Matchup card confidence badge |
| Low confidence | `#6b7280` | Matchup card confidence badge / muted text |
| "NO BET" red | `#991b1b` | Matchup card no-bet badge |
| Magenta (primary) | `#D6286A` / `#F03060` | Streamlit primary buttons |
| Navy text | `#100030` | Brand anchor |
| Betting-oracle link | `#3b82f6` | Footer "Powered by" link |

### 1.3 Layout constants

- `st.set_page_config(..., layout="wide", initial_sidebar_state="expanded")`
- Sidebar width: Streamlit default (~320 px).
- Main column widths: `st.columns([1, 4])` for header, `[5, 2]` for matchup
  row, `[3, 2]` for game card row, `[1, 1, 1, 1]` for metric rows.

### 1.4 Sidebar logo

`footer.add_sidebar_logo(width=120)` renders
`data_files/logo_no_words.png` (the WNBA silhouette) at the top of every
sub-page. The home page does not draw this; it shows
`data_files/logo.png` (the full logo with words) in the header at width=130.

### 1.5 Footer

`footer.add_betting_oracle_footer()` writes a centred HTML banner with the
Betting Oracle wordmark, "Sports Prediction Analytics" caption, and a link
back to `https://www.betting-oracle.com`. Every page includes it.

### 1.6 Header treatment (home page only)

```html
<div class="row" style="grid-template-columns: 1fr 4fr">
  <img src="data_files/logo.png" width=130 />
  <h1>WNBA Predictions</h1>
  <p style="color:#888">Season {year} · {current_date}</p>
</div>
<hr/>
```

Sub-pages do not render this header; they put the logo in the sidebar and
start directly with `st.title("🏀 Game Predictions")` etc.

---

## 2. Navigation

`st.navigation` is configured at the bottom of `predictions.py` and groups
pages under four section headers:

| Section | Pages |
|---|---|
| (root) | Home (default) |
| Predictions | Game Predictions, Scenario Lab |
| Stats | Standings, Team Stats, Player Stats |
| Models | Model Performance, Data Health |

Section headers are rendered as non-clickable label rows in the sidebar.

Page icons:

| Page | Icon |
| --- | --- |
| Home | 🏠 |
| Game Predictions | 🏀 |
| Scenario Lab | 🧪 |
| Standings | 🏆 |
| Team Stats | 📊 |
| Player Stats | 👤 |
| Model Performance | 📈 |
| Data Health | 🩺 |

---

## 3. Per-page visual inventory

### 3.1 Home (`predictions.py:home_page`)

- Top row: `[logo 130px][title + subtitle]`, then `<hr/>`.
- Subtitle: `Season {year} · {Weekday, Month DD, YYYY}` in `#888`.
- Release-gate `st.error("Paper-only shadow mode: ...")` if gate is not
  `production_ready`.
- Hero metrics row: 5 `st.metric` tiles:
  1. Upcoming Games
  2. High Confidence
  3. Medium Confidence
  4. Avg Conviction (`{p:.0%}`)
  5. `2025 Holdout Accuracy` (`{p:.1%}`, tooltip references
     `scripts/train_models.py`)
- `<hr/>`
- Matchup cards: each row uses `st.container(border=True)` and inside it a
  two-column row `[5, 2]`:
  - left: bold `Away @ Home`, then 22px-tall probability bar with home/away
    percentages inside (white text on blue/red) and a muted row with team
    names below.
  - right: confidence badge or `NO BET · PAPER ONLY` red pill; below it
    either `Pick: {favorite}` or the no-bet reason in muted caption.
- Empty state: `st.info("No upcoming games found, or data hasn't been
  generated yet. Run scripts/daily_update.py to populate.")`.
- `<hr/>`
- "### 🏀 Upcoming Matchups ({count})" heading before cards.
- `### Explore` heading + five navigation tiles in
  `st.columns(5)` with `st.container(border=True)`:
  1. 🏀 Game Predictions → `pages/1_Game_Predictions.py`
  2. 🏆 Standings → `pages/3_Standings.py`
  3. 📊 Team Stats → `pages/4_Team_Stats.py`
  4. 👤 Player Stats → `pages/5_Player_Stats.py`
  5. 📈 Model Performance → `pages/6_Model_Performance.py`
- Footer.

### 3.2 Game Predictions (`pages/1_Game_Predictions.py`)

- Title: `🏀 Game Predictions`.
- Caption: "Probabilistic projections with as-of availability, minutes,
  lineup, and workload context."
- Page-level warnings:
  - `st.warning(...)` when `release_gate_status == "limited_paper"`.
  - `st.error(...)` for any other non-`production_ready` gate status.
- One card per game (`st.container(border=True)`). Inside:
  - `[3, 2]` top row:
    - left: caption with formatted scheduled time
      (`{Weekday}, {Mon} {DD} · {HH}:{MM} {AM/PM} ET`); heading
      `### Away @ Home`; probability bar (24px tall — 2px taller than the
      home page bar).
    - right: `st.error("NO BET · PAPER ONLY")` or
      `st.success("X confidence")`; caption
      `Snapshot: {stage} · {generated_at}`.
  - `[1, 1, 1, 1]` metrics: Home win %, Home margin (± with 90% interval
    in tooltip), Total (with 90% interval tooltip), Scenario uncertainty
    (pts).
  - 4 column captions: market home prob, market spread, market total,
    edge vs market.
  - `st.tabs([...])`:
    1. **Rotation scenario** — `_availability_editor(game, rotation)`:
       - Heading `Rotation and availability scenario editor`.
       - Caption explaining the editor is local-only.
       - `st.data_editor` on the rotation frame with disabled columns
         except `availability_probability` and `minutes_mean_if_active`.
       - Three live metrics: scenario home margin (±), scenario margin SD,
         availability-only uncertainty.
       - Optional `st.warning` "No bet: the edited availability uncertainty
         is larger than the apparent spread edge."
    2. **Lineup matchup** — `_lineup_view(lineup)`. Heading `Lineup matchup
       and minutes uncertainty`; caption or dataframe; or
       `st.info("No source lineup or inferred top-five rotation is
       available.")`.
    3. **Travel & context** — `_workload_view(context)`. Heading `Travel
       and workload timeline`; chip list of context labels; dataframe of
       per-side rest/workload/travel; optional "Verified overseas workload"
       dataframe.
    4. **Provenance** — `st.json({model_version, feature_schema_version,
       release_gate_status, availability_status, stage, generated_at})`.
- Footer caption: "Informational analysis only. The application never
  recommends Kelly staking while the release gate is closed."

### 3.3 Scenario Lab (`pages/2_Scenario_Lab.py`)

- Title: `🧪 Scenario Lab`.
- Top-level `st.error("Paper-only. Player props require minutes uncertainty;
  parlays use dependence simulation; Kelly is disabled.")`.
- `st.tabs(["Player prop", "Parlay dependence", "Staking policy"])`.

**Player prop tab** (`prop_tab`):
- Caption: "This analytical calculator integrates the probability of
  playing and the player's minutes distribution."
- `st.columns(3)`:
  - left: rate per minute (default 0.65, step 0.05), rate SD (default 0.12)
  - middle: expected minutes if active (default 31, step 1), minutes SD
    (default 5, step 0.5)
  - right: availability probability slider (0–1, default 0.85), prop line
    (default 19.5, step 0.5)
- Three `st.metric` outputs: Projected mean (1 dp), Over probability (%),
  Under probability (%).
- Optional `st.warning("No bet: {reason}")` for `no_bet` status.

**Parlay dependence tab** (`parlay_tab`):
- Caption: "Positive correlation can materially change a multi-leg
  probability; independence is shown only as a comparator."
- Three leg sliders (defaults 0.58, 0.56, 0.54) plus a shared correlation
  slider (-0.50–0.90, default 0.25, step 0.05).
- Three `st.metric`: Simulated joint hit, Independence estimate, Dependence
  adjustment.

**Staking policy tab** (`policy_tab`):
- `st.json(staking_policy(release_gate_passed=...))` (shows
  `live_stake_units`, `paper_stake_units`, `kelly_enabled`, `reason`).
- Caption: "Season-futures simulation is available in
  `utils.market_simulation.simulate_season_futures` for pipeline use."

### 3.4 Standings (`pages/3_Standings.py`)

- Sidebar: `st.sidebar.selectbox("Season", descending list of seasons)`.
- Title: `🏆 WNBA Standings — {season}`.
- If standings not empty and `Conference` is present:
  - For each conference group, `st.subheader(conf)` followed by a
    `st.dataframe` of the friendly-mapped columns sorted by `Wins` desc.
- Friendly column mapping (`COLUMN_SPECS`):
  `TeamName → Team`, `WINS → Wins`, `LOSSES → Losses`, `WinPCT → Win %`
  (formatted `{:.3f}`), `strCurrentStreak → Streak`, `PlayoffRank →
  Playoff Rank`, `Conference → Conference`, `HOME → Home Record`,
  `ROAD → Road Record`, `L10 → Last 10`, `PointsPG → Points/Game`,
  `OppPointsPG → Opp Points/Game`, `DiffPointsPG → Point Diff`.
- Empty state: `st.info("No standings data available. Run
  scripts/daily_update.py to fetch.")`.

### 3.5 Team Stats (`pages/4_Team_Stats.py`)

- Sidebar: season selector.
- Title: `📊 Team Stats — {season}`.
- Team selector (`st.selectbox`) of `canonical_team_id`s from the season,
  labelled with `display_name` from the reference table.
- Recent form metrics: 4 `st.metric` for Win% (L10), Pts/Game (L10),
  Rest Days, Streak (the last shown with explicit `+` sign).
- `st.subheader("Game Log")`: dataframe with `game_date`, `opponent_team_id`,
  `is_home` (mapped to "Home"/"Away"), `points`, `win` (mapped to "W"/"L"),
  tail(15) reversed.
- `st.subheader("Points Per Game (rolling)")`: `st.line_chart` of
  `points` + `points_L10` indexed by `game_date`.
- Empty state: `st.info("No team game stats available. Run
  scripts/fetch_historical.py to populate.")`.

### 3.6 Player Stats (`pages/5_Player_Stats.py`)

- Sidebar: season selector.
- Title: `👤 Player Stats — {season}`.
- Player selector (`st.selectbox`) with `display_name` mapping.
- Four `st.metric`: Games, Pts/Game, Pts/40 (L10), Ast/40 (L10).
- `st.subheader("Recent Game Log")`: dataframe of `game_date`, `points`,
  `rebounds`, `assists`, `minutes`, `points_per40` (tail 15 reversed).
- Optional `st.subheader("Points Per Game")` + `st.line_chart` (when ≥3
  games exist).
- Empty state: `st.info("No player game stats available. Run
  scripts/fetch_historical.py to populate.")`.

### 3.7 Model Performance (`pages/6_Model_Performance.py`)

- Title: `📈 Model Performance`.
- `st.subheader("Production release gate")`:
  - `st.success("Production release gate passed.")` when `status ==
    "production_ready"`, else `st.error("Shadow/paper-only artifact.
    Live betting use is suspended.")`.
  - One `st.metric` per check in `release_gate.checks` showing `PASS`/
    `FAIL`. (Implemented as inline cols built from the dict.)
  - Caption: `Rows: {n_rows:,} · Seasons: {seasons} · Untouched holdout:
    {holdout_season} ({holdout_rows:,} games)`.
- `st.subheader("Untouched 2025 winner score")`:
  - Four `st.metric`: Accuracy (%), Log loss (3 dp), Brier score (3 dp),
    Games (int).
  - Caption: "Winner calibration: ECE {ece:.3f} · maximum calibration
    error {mce:.3f}".
  - `st.expander("Winner reliability bins")` → dataframe of bins.
- `st.subheader("Calibrated continuous distributions")`:
  - Dataframe with `target`, `MAE`, `RMSE`, `CRPS`, `90% coverage`,
    `residual SD` for Margin and Total.
  - `st.info("No recent-season distribution score is available yet.")` if
    empty.
- `st.subheader("Expanding-season folds with recency weighting")` (only if
  folds present): dataframe.
- `st.subheader("Baselines and market-relative scoring")`:
  - Rows for Elo, Simple Efficiency (with model/market metrics), and
    (when market data exists) Model on priced games / De-vigged close.
- `st.subheader("Line-bucket calibration")` (only if any present):
  two-column spread/total dataframes.
- `st.subheader("2026 frozen paper ledger")`:
  - Four `st.metric`: Priced bets (help text mentions 300-bet threshold),
    Graded bets, Mean CLV, Flat-stake ROI.
  - Dataframe of `by_market`.
  - `st.expander("Frozen bet records")` → full ledger dataframe.
- `st.subheader("Drift and automatic suspension")`:
  - `st.error("Suspended: maximum PSI is {max_psi:.3f} (threshold 0.25).")`
    if suspended, else `st.success("Drift clear: maximum PSI is
    {max_psi:.3f}.")`.
  - Caption: "Shifted features: ..." if any.
- `st.subheader("Performance by WNBA context")`: `st.tabs` per segment
  (`travel`, `rest`, `roster_continuity`, `season_phase`, `data_source`),
  each with its own dataframe (or muted caption if empty).
- Caption: "Artifacts: `{model_dir()}`".

### 3.8 Data Health (`pages/7_Data_Health.py`)

- Title: `🩺 Data Health`.
- Caption: "Source metadata drives this panel; missing and stale
  observations are never silently substituted."
- `st.subheader("Adapter source status")`: dataframe of source, data_type,
  status (mapped to Healthy/Failed/Unknown from `ok`), last_success,
  last_attempt, age_hours (computed at render time from now UTC),
  records, error.
- Optional `st.warning("{n} source/data combinations failed their latest
  attempt.")`.
- `st.subheader("Capability and fallback registry")`: dataframe of
  data_type, priority (int), source — flattened from `SOURCE_PRIORITY`.
- `st.subheader("Artifact safety")`: four `st.metric`: League
  (`cfg.display_name`), Season, Schema (`"2.0.0"`), Artifact (gate status
  with `_` → space, title-cased).
  - `st.error("Stale/unvalidated artifacts are automatically presented as
    no-bet, paper-only projections.")` if gate is not production-ready.
- `st.subheader("As-of coverage expectations")`: static dataframe of
  dataset → required history → policy.

---

## 4. Empty / error states (recurring patterns)

| State | Visual | Used on |
|---|---|---|
| "No data" info | `st.info` | every data-driven page |
| No-bet paper-only | red `st.error` pill (`NO BET · PAPER ONLY`) | matchup cards |
| Release-gate not passed | red `st.error` block | Home, Game Predictions |
| Limited paper | yellow `st.warning` block | Game Predictions |
| Drift suspended | red `st.error` block | Model Performance |
| Provider failed | yellow `st.warning` block | Data Health |

---

## 5. Responsive behaviour

Streamlit's `layout="wide"` means pages already use full viewport width.
Mobile behaviour comes from Streamlit's own column-stacking (sidebar
collapses to a hamburger). No custom CSS responsive rules are present in
the WNBA Streamlit app, so the React port should adopt the same default
behaviour with minimal responsive tweaks (avoid horizontal scrolling on
small viewports).

---

## 6. Baseline screenshots

Baseline Streamlit screenshots for the eight pages at desktop (1440×900)
and mobile (390×844) are captured during Phase 5 into
`docs/react-migration/parity/<page>/streamlit-desktop.png` and
`streamlit-mobile.png` and compared against the corresponding React
screenshots produced by `scripts/test_playwright.py` against the
`frontend/` dev server.