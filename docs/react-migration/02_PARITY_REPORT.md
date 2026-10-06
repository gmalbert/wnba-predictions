# 02 — Parity Report (Streamlit vs React)

> **Purpose.** Page-by-page parity verdict required by §50 of
> `docs/WNBA_CLOUDFLARE_REACT_CONVERSION.md`. Compares the Streamlit
> reference app (`predictions.py` + `pages/`) against the React port
> (`frontend/`) running on identical exported data
> (`frontend/public/data/`, produced by `scripts/export_web_data.py`).
>
> **Method.** `scripts/test_react_parity.py` drives both apps with
> Playwright (Chromium) at desktop 1440×900 and mobile 390×844, asserts
> page-expected text, captures screenshots into
> `docs/react-migration/parity/<page>/`, records console errors, and
> writes perf metrics into `docs/react-migration/perf/`.
>
> **Run.** 2026-09-27 21:18–21:20 local (America/New_York).
> Streamlit 8501 (python 3.13, `predictions.py`), React 4173
> (`vite preview` of `frontend/dist`, bundle `index-*.js` 223 KB /
> 70 KB gzip). **Zero console errors on both sides** (see
> `perf/console-errors.json`). Streamlit rendered its night-time Wine
> Violet theme (`#120B1C`), the same palette the React app uses
> statically, so the screenshots below are directly comparable.

---

## 1. Verdict summary

| Page | Functional parity | Visual parity | Responsive parity | Data parity |
|---|---|---|---|---|
| Home | PASS | PASS | PASS | PASS |
| Game Predictions | PASS | PASS | PASS | PASS |
| Scenario Lab | PASS | PASS | PASS | PASS¹ |
| Standings | PASS | PASS | PASS | PASS |
| Team Stats | PASS | PASS | PASS | PASS |
| Player Stats | PASS | PASS | PASS | PASS |
| Model Performance | PASS | PASS | PASS | PASS |
| Data Health | PASS | PASS | PASS | PASS |

¹ Scenario Lab Monte-Carlo probabilities differ by ≤ 0.4 pp because the
two apps use different RNG streams by design (see §3.4). The TS port is
verified bit-for-bit against the Python fixture generator; see
`frontend/tests/test_scenario_parity.ts` (12/12 fixtures pass).

All PASS verdicts are subject to the explicitly documented low-severity
framework-rendering differences in §3. No critical or high-severity
parity issues remain open.

Parity issues **found and fixed during this pass** (all verified in the
final screenshots):

| # | Issue | Fix |
|---|---|---|
| 1 | Home "Avg Conviction" showed `—` (React averaged only `status == "ready"` games; Streamlit averages all) | `frontend/src/pages/Home.tsx` now averages over all games → `70%` both sides |
| 2 | Footer logo: React showed the WNBA logo; Streamlit shows the Betting Oracle logo (hot-linked from GitHub) | React now ships a local 240×366 copy (`frontend/public/betting-oracle-logo.png`, 108 KB) so the frontend keeps its no-external-network rule |
| 3 | Standings showed full team names and abbreviated headers | Exporter now emits `nickname` (raw `TeamName`); React renders nickname + full `COLUMN_SPECS` headers incl. `Conference` |
| 4 | Team/Player Stats defaulted to a different team/player (string sort of ids) | Numeric sort, matching `sorted(canonical_ids)` in Streamlit → both default to Dallas Wings / DeWanna Bonner |
| 5 | Team Stats L10 metrics differed (React 60 %/91.2 vs Streamlit 70 %/90.9) | Exporter `_team_rolling_features` now uses pre-game shifted rolling means (`.shift(1)`, `min_periods` 1 for win pct, 5 for points), matching `utils.feature_engine` |
| 6 | Data Health rows alphabetised; Streamlit uses registry order | Exporter no longer sorts `sources` |
| 7 | Release-gate checks alphabetised (JSON key sort); Streamlit uses pipeline order | React restores canonical order `untouched → 300 bets → CLV → drift` |
| 8 | Game Predictions timestamps localised (`8/25/2026, 9:30:53 PM` / `EDT`) | React now renders raw `generated_at` and `… · 07:00 PM ET`, matching Streamlit byte-for-byte |
| 9 | Streamlit screenshots caught half-rendered pages (empty metric boxes) | Harness post-hydration wait raised 2 s → 5 s for late websocket deltas |
| 10 | Raw-vs-friendly table headers on Team/Player Stats, Data Health, Model Performance distributions | React tables now use the same raw column names and value formatting as `st.dataframe` (incl. `None`, ≤4-dp floats, pandas-style `YYYY-MM-DD 00:00:00` dates) |

---

## 2. Per-page detail

Required fields per §50: page · feature · Streamlit result · React
result · functional status · visual status · known difference · reason ·
severity · screenshot/evidence reference.

### 2.1 Home — `parity/home/{streamlit,react}-{desktop,mobile}.png`

| Feature | Streamlit result | React result | Functional | Visual | Known difference | Reason | Severity |
|---|---|---|---|---|---|---|---|
| Header (logo + title + subtitle) | Full logo, "WNBA Predictions", "Season 2026 · Sunday, September 27, 2026" | Identical | PASS | PASS | — | — | — |
| Release-gate banner | `st.error` "Paper-only shadow mode: … has not passed." | Identical copy, error banner | PASS | PASS | — | — | — |
| Hero metrics | 44 / 0 / 0 / 70 % / 66.1 % | Identical | PASS | PASS | React tiles are boxed cards; `st.metric` is unboxed | React `MetricCard` chrome | Low |
| Avg Conviction tooltip | none | none | PASS | PASS | — | — | — |
| Matchup cards (44) | Same order, teams, probs, spreads, `NO BET · PAPER ONLY` pill + reason | Identical | PASS | PASS | — | — | — |
| Probability bar | WNBA blue `#1D428A` / red `#C8102E`, 22 px | Same colours, same height | PASS | PASS | — | — | — |
| Explore tiles (5) | icon + page link + caption | Identical set/order | PASS | PASS | — | — | — |
| Freshness caption | none | "Data generated at … · model … · feature schema …" | PASS | PASS | Additive line | §43 freshness UX | Low |
| Footer | Betting Oracle banner + logo | Identical (local logo copy) | PASS | PASS | — | — | — |

### 2.2 Game Predictions — `parity/game-predictions/…`

| Feature | Streamlit result | React result | Functional | Visual | Known difference | Reason | Severity |
|---|---|---|---|---|---|---|---|
| Title + caption | "🏀 Game Predictions" + caption | Identical | PASS | PASS | — | — | — |
| Gate banner | `st.error` paper-only copy | Identical | PASS | PASS | — | — | — |
| Game time | "Wed, Aug 26 · 07:00 PM ET" | Identical string | PASS | PASS | — | — | — |
| Snapshot caption | "Snapshot: pre_tip · 2026-08-26T01:30:53+00:00" | Identical (raw ISO) | PASS | PASS | — | — | — |
| Metrics row | 17.8 % / -14.3 / 171.2 / 0.0 pts | Identical | PASS | PASS | Boxed vs unboxed tiles; `st.metric` tooltips become native `title` attrs | Framework | Low |
| Market captions | 13.3 % / +13.4 / 150.6 / +4.5 % | Identical | PASS | PASS | — | — | — |
| Tabs | Rotation scenario · Lineup matchup · Travel & context · Provenance | Identical set/order | PASS | PASS | — | — | — |
| Rotation editor | `st.data_editor`, 99 % play, minutes shown rounded by the widget, scenario metrics + no-bet warning | Same players/values; native number inputs show full precision (23.04608) | PASS | PASS | Cell number formatting in the editable widget | `st.data_editor` display rounding vs raw `<input>` | Low |
| Provenance tab | `st.json` of 6 keys | Same 6 keys as formatted JSON | PASS | PASS | — | — | — |
| Closing caption | "Informational analysis only…" | Identical | PASS | PASS | — | — | — |

### 2.3 Scenario Lab — `parity/scenario-lab/…`

| Feature | Streamlit result | React result | Functional | Visual | Known difference | Reason | Severity |
|---|---|---|---|---|---|---|---|
| Tabs | Player prop · Parlay dependence · Staking policy | Identical | PASS | PASS | — | — | — |
| Prop inputs | 3-col layout: rate/minutes/availability, then rate SD/minutes SD/line; defaults 0.65/31/0.85/0.12/5/19.5 | Identical layout + defaults | PASS | PASS | Slider value shown beside label (React) vs beside slider (Streamlit) | Framework | Low |
| Prop outputs | mean 17.1, over 44.5 %, under 55.5 % | mean 17.1, over 44.9 %, under 55.1 % | PASS | PASS | ±0.4 pp on MC probabilities | Different RNG streams by design (§3.4) | Low (documented) |
| Parlay tab | 3 leg sliders + correlation slider, 3 metrics | Identical controls/metrics | PASS | PASS | Same RNG note | Same | Low |
| Staking policy | `st.json` of policy dict | Same dict from `scenario_policy.json` | PASS | PASS | — | — | — |
| Footer | Betting Oracle banner + logo | Identical (local copy) | PASS | PASS | — | — | — |

### 2.4 Standings — `parity/standings/…`

| Feature | Streamlit result | React result | Functional | Visual | Known difference | Reason | Severity |
|---|---|---|---|---|---|---|---|
| Title | "🏆 WNBA Standings — 2026" | Identical | PASS | PASS | — | — | — |
| Season selector | In sidebar | Top of main column | PASS | PASS | Control placement | React Router owns the sidebar; page controls live in the outlet | Low |
| Conference groups | East then West, `st.subheader` + dataframe | Identical grouping/order | PASS | PASS | — | — | — |
| Columns | Team(nickname), Wins, Losses, Win %, Streak, Playoff Rank, Conference, Home Record, Road Record, Last 10, Points/Game, Opp Points/Game, Point Diff | Identical labels/order/values | PASS | PASS | — | — | — |
| Rows | Dream 19-11 … Sun 7-23; Lynx 25-6 … Storm 6-27 | Identical | PASS | PASS | — | — | — |

### 2.5 Team Stats — `parity/team-stats/…`

| Feature | Streamlit result | React result | Functional | Visual | Known difference | Reason | Severity |
|---|---|---|---|---|---|---|---|
| Default selection | Dallas Wings (smallest canonical id) | Dallas Wings | PASS | PASS | — | — | — |
| Recent form metrics | 70 % / 90.9 / 3 / +9 | Identical | PASS | PASS | Boxed vs unboxed tiles | Framework | Low |
| Game Log | Raw headers, 15 rows reversed, `None` opponent ids, pandas dates | Identical content/format | PASS | PASS | `st.dataframe` shows the pandas index column; React does not | Framework | Low |
| Rolling chart | `st.line_chart` points + points_L10 | Inline SVG, same two series, same colours (blue/red) | PASS | PASS | Chart chrome (axis ticks, hover) | No chart library by design (§3.5 of handoff) | Low |

### 2.6 Player Stats — `parity/player-stats/…`

| Feature | Streamlit result | React result | Functional | Visual | Known difference | Reason | Severity |
|---|---|---|---|---|---|---|---|
| Default selection | DeWanna Bonner | DeWanna Bonner | PASS | PASS | — | — | — |
| Summary metrics | 35 / 10.2 / 18.1 / 2.8 | Identical | PASS | PASS | Boxed vs unboxed tiles | Framework | Low |
| Recent Game Log | Raw headers, ≤4-dp floats (`16.2963`, `31.25`, `20`) | Identical values/format | PASS | PASS | Index column (as above) | Framework | Low |
| Points chart | `st.line_chart` single series | Inline SVG, same series | PASS | PASS | Chart chrome | As above | Low |

### 2.7 Model Performance — `parity/model-performance/…`

| Feature | Streamlit result | React result | Functional | Visual | Known difference | Reason | Severity |
|---|---|---|---|---|---|---|---|
| Gate banner | `st.error` shadow/paper-only | Identical | PASS | PASS | — | — | — |
| Gate checks | PASS / FAIL / FAIL / PASS in pipeline order | Identical order/values | PASS | PASS | React tiles tinted red/green | Presentational addition | Low |
| Rows/seasons caption | "Rows: 1,916 · Seasons: [2018, …] · Untouched holdout: 2025 (327 games)" | Identical (brackets included) | PASS | PASS | — | — | — |
| Winner score | 66.1 % / 0.654 / 0.226 / 327 + ECE caption | Identical | PASS | PASS | — | — | — |
| Reliability bins | Collapsed expander | Collapsed `<details>` | PASS | PASS | — | — | — |
| Distributions | target/MAE/RMSE/CRPS/90 % coverage/residual SD, raw values (`8.36`) | Identical labels/values | PASS | PASS | — | — | — |
| Walk-forward folds | 5 rows, same numbers | Identical | PASS | PASS | — | — | — |
| Baselines / ledger / drift / segments | Same sections, same values | Identical | PASS | PASS | — | — | — |

### 2.8 Data Health — `parity/data-health/…`

| Feature | Streamlit result | React result | Functional | Visual | Known difference | Reason | Severity |
|---|---|---|---|---|---|---|---|
| Source status table | Registry order, raw headers, raw ISO timestamps, `None`, age_hours at render | Identical order/headers/values (age_hours computed at render, matches) | PASS | PASS | `st.dataframe` viewport clips at ~10 rows with in-frame scroll; React table shows all 14 rows | Framework | Low |
| Failure warning | "9 source/data combinations failed their latest attempt." | Identical | PASS | PASS | — | — | — |
| Capability registry | data type / priority / source rows | Identical | PASS | PASS | — | — | — |
| Artifact safety | WNBA / 2026 / 2.0.0 / Shadow Only + error banner | Identical | PASS | PASS | — | — | — |
| Training coverage caption | seasons list with brackets | Identical | PASS | PASS | — | — | — |
| As-of coverage | 5 static rows | Identical | PASS | PASS | — | — | — |

---

## 3. Known differences (framework-level, all low severity)

Per §50, these are unavoidable framework-rendering or deliberate
architecture differences. None affects data, state, or behaviour.

| # | Difference | Pages | Reason |
|---|---|---|---|
| 3.1 | **Theme switching.** Streamlit swaps between a daytime and night-time palette based on browser-local time (`utils.theme_utils`); React renders the night-time Wine Violet palette statically. Screenshots in this report were taken at 21:18 local, so both sides show the identical dark palette. | all | React has no config-rewriting runtime; the dark palette is the audit-time default (`00A_VISUAL_REFERENCE.md` §1.1) |
| 3.2 | **Sidebar logo position.** React pins the wordmark-free logo to the top of the sidebar; Streamlit's `st.sidebar.image` appends it below the auto-rendered nav menu. | all (sub-pages) | Streamlit renders the `st.navigation` menu before any `st.sidebar.*` calls |
| 3.3 | **Mobile navigation.** Streamlit overlays the sidebar with a `<<` collapse control; React stacks the nav above the content (CSS `@media ≤ 900 px`). Both avoid horizontal scrolling; all content reachable. | all | No hamburger menu in the React shell (minimal responsive tweak per `00A` §5) |
| 3.4 | **Scenario Lab MC probabilities.** Over/under differ by ≤ 0.4 pp (e.g. 44.5 % vs 44.9 %). Production Python uses `numpy.random.default_rng` (PCG64); the TS port uses Mulberry32 for bit-identical parity with the Python fixture generator. The TS port passes 12/12 fixtures at 1e-6 (prop) / 0.01 (parlay) tolerance. | Scenario Lab | Deliberate: fixtures must be bit-comparable; production path untouched (HANDOFF §5.3) |
| 3.5 | **Metric tile chrome.** React `MetricCard` renders a boxed card; `st.metric` is unboxed text. Values, labels, order identical. | Home, Game Predictions, Team/Player Stats, Model Performance, Data Health | Presentational |
| 3.6 | **Tooltips.** `st.metric(help=…)` hover icons become native `title` attributes in React (same text). | Game Predictions, Home | Framework |
| 3.7 | **Table viewport.** `st.dataframe` clips long tables with an in-frame scrollbar and shows the pandas index; React tables render all rows without an index column. Row order/content identical. | Standings, Team/Player Stats, Data Health, Model Performance | Framework |
| 3.8 | **Rotation editor cell display.** `st.data_editor` NumberColumn displays minutes rounded (23); React's raw number input shows full precision (23.04608). Underlying values identical; both editable. | Game Predictions | Widget display formatting |
| 3.9 | **Nav section labels.** React renders group labels in all-caps (PREDICTIONS/STATS/MODELS); Streamlit renders title case. | all | CSS `text-transform` |
| 3.10 | **Additive freshness caption.** React Home adds "Data generated at … · model … · feature schema …" (§43 freshness UX); Streamlit Home has no equivalent line. | Home | Intentional addition, required by the runbook's freshness-UX section |
| 3.11 | **Chart chrome.** React uses a dependency-free inline-SVG line chart (same series, same blue/red colours); `st.line_chart` (Vega-Lite) has richer axis/hover chrome. | Team Stats, Player Stats | Bundle budget (~70 KB gzip total) |

---

## 4. Evidence index

| Page | Streamlit desktop | React desktop | Streamlit mobile | React mobile |
|---|---|---|---|---|
| Home | `parity/home/streamlit-desktop.png` | `parity/home/react-desktop.png` | `parity/home/streamlit-mobile.png` | `parity/home/react-mobile.png` |
| Game Predictions | `parity/game-predictions/streamlit-desktop.png` | `parity/game-predictions/react-desktop.png` | `parity/game-predictions/streamlit-mobile.png` | `parity/game-predictions/react-mobile.png` |
| Scenario Lab | `parity/scenario-lab/streamlit-desktop.png` | `parity/scenario-lab/react-desktop.png` | `parity/scenario-lab/streamlit-mobile.png` | `parity/scenario-lab/react-mobile.png` |
| Standings | `parity/standings/streamlit-desktop.png` | `parity/standings/react-desktop.png` | `parity/standings/streamlit-mobile.png` | `parity/standings/react-mobile.png` |
| Team Stats | `parity/team-stats/streamlit-desktop.png` | `parity/team-stats/react-desktop.png` | `parity/team-stats/streamlit-mobile.png` | `parity/team-stats/react-mobile.png` |
| Player Stats | `parity/player-stats/streamlit-desktop.png` | `parity/player-stats/react-desktop.png` | `parity/player-stats/streamlit-mobile.png` | `parity/player-stats/react-mobile.png` |
| Model Performance | `parity/model-performance/streamlit-desktop.png` | `parity/model-performance/react-desktop.png` | `parity/model-performance/streamlit-mobile.png` | `parity/model-performance/react-mobile.png` |
| Data Health | `parity/data-health/streamlit-desktop.png` | `parity/data-health/react-desktop.png` | `parity/data-health/streamlit-mobile.png` | `parity/data-health/react-mobile.png` |

Console-error evidence: `perf/console-errors.json` (all empty).
Scenario-math evidence: `tests/fixtures/scenario_lab_parity.json` +
`frontend/tests/test_scenario_parity.ts` (12/12 pass).
Performance evidence: `perf/react.json`, `perf/streamlit.json` (see
`03_PERFORMANCE_REPORT.md`).

## 5. How to reproduce

```powershell
# Terminal 1
python -m streamlit run predictions.py --server.port 8501 --server.headless true --server.address 127.0.0.1
# Terminal 2 (after `npm run build` in frontend/)
frontend\node_modules\.bin\vite.cmd preview --port 4173 --strictPort
# Terminal 3
python scripts\test_react_parity.py   # exits 0; rewrites parity/ + perf/
```
