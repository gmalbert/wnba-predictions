# 03 — Performance Report (Streamlit vs React)

> **Purpose.** Side-by-side browser performance comparison required by
> the migration Goal (§35 of `docs/WNBA_CLOUDFLARE_REACT_CONVERSION.md`).
> Metrics come from `scripts/test_react_parity.py`, which measures each
> route in a **fresh Playwright browser context** (no shared HTTP cache)
> at desktop 1440×900 and writes `perf/react.json` / `perf/streamlit.json`.
>
> **Run.** 2026-09-27 21:18–21:20 local. Streamlit 8501 (`predictions.py`,
> python 3.13), React 4173 (`vite preview` of the production `dist/`).
> Localhost loopback, so network latency is ~0 and differences are
> payload + parse + render costs, not RTT.

## 1. Headline

**React is faster than Streamlit on every measured metric on every
route. There is no regression to call out.** The worst (i.e. smallest)
React advantage is on the Home route, and even there React paints first
content ~2.3× sooner and transfers ~3.6× fewer bytes.

| Metric (route range) | Streamlit | React | React advantage |
|---|---|---|---|
| First contentful paint | 500–656 ms | 128–220 ms | **2.3–4.1× faster** |
| DOM content loaded | 339–456 ms | 29–53 ms | **~9–13× faster** |
| Load event | 339–456 ms | 29–53 ms | **~9–13× faster** |
| Total transferred | 3.97–5.87 MB | 0.54–1.09 MB | **4.2–9.5× smaller** |
| JS requests | 135–172 | 1 | **135–172× fewer** |
| JS transferred | 3.37–5.28 MB | 70 KB | **48–75× smaller** |

## 2. Per-route comparison

FCP = first-contentful-paint (ms) · DCL = DOMContentLoaded (ms) ·
Load = load event (ms) · Bytes = total transferred · JS req = JS request
count · JS bytes = JS transferred.

### Home (`/`)

| App | FCP | DCL | Load | Bytes | JS req | JS bytes |
|---|---|---|---|---|---|---|
| Streamlit | 500 | 384.1 | 384.1 | 3,965,463 | 135 | 3,371,539 |
| React | 220 | 52.7 | 52.7 | 1,090,180 | 1 | 70,250 |
| Δ | −280 ms | −331 ms | −331 ms | −2.88 MB | −134 | −3.30 MB |

### Game Predictions (`/game-predictions` vs `/Game_Predictions`)

| App | FCP | DCL | Load | Bytes | JS req | JS bytes |
|---|---|---|---|---|---|---|
| Streamlit | 576 | 387.5 | 387.5 | 5,874,197 | 158 | 5,275,723 |
| React | 156 | 39.8 | 40.1 | 621,079 | 1 | 70,250 |
| Δ | −420 ms | −348 ms | −347 ms | −5.25 MB | −157 | −5.21 MB |

### Scenario Lab (`/scenario-lab` vs `/Scenario_Lab`)

| App | FCP | DCL | Load | Bytes | JS req | JS bytes |
|---|---|---|---|---|---|---|
| Streamlit | 556 | 363.5 | 363.6 | 4,219,760 | 153 | 3,633,862 |
| React | 152 | 33.3 | 33.3 | 537,603 | 1 | 70,250 |
| Δ | −404 ms | −330 ms | −330 ms | −3.68 MB | −152 | −3.56 MB |

### Standings (`/standings` vs `/Standings`)

| App | FCP | DCL | Load | Bytes | JS req | JS bytes |
|---|---|---|---|---|---|---|
| Streamlit | 524 | 338.6 | 338.6 | 5,715,727 | 168 | 5,117,253 |
| React | 152 | 35.7 | 35.7 | 539,387 | 1 | 70,250 |
| Δ | −372 ms | −303 ms | −303 ms | −5.18 MB | −167 | −5.05 MB |

### Team Stats (`/team-stats` vs `/Team_Stats`)

| App | FCP | DCL | Load | Bytes | JS req | JS bytes |
|---|---|---|---|---|---|---|
| Streamlit | 564 | 381.3 | 381.3 | 5,739,466 | 172 | 5,140,992 |
| React | 136 | 32.9 | 33.3 | 550,638 | 1 | 70,250 |
| Δ | −428 ms | −348 ms | −348 ms | −5.19 MB | −171 | −5.07 MB |

### Player Stats (`/player-stats` vs `/Player_Stats`)

| App | FCP | DCL | Load | Bytes | JS req | JS bytes |
|---|---|---|---|---|---|---|
| Streamlit | 596 | 373.5 | 373.5 | 5,739,466 | 172 | 5,140,992 |
| React | 128 | 29.1 | 29.2 | 682,852 | 1 | 70,250 |
| Δ | −468 ms | −344 ms | −344 ms | −5.06 MB | −171 | −5.07 MB |

### Model Performance (`/model-performance` vs `/Model_Performance`)

| App | FCP | DCL | Load | Bytes | JS req | JS bytes |
|---|---|---|---|---|---|---|
| Streamlit | 608 | 413.9 | 413.9 | 5,694,385 | 155 | 5,005,487 |
| React | 128 | 31.4 | 31.7 | 539,047 | 1 | 70,250 |
| Δ | −480 ms | −382 ms | −382 ms | −5.16 MB | −154 | −4.94 MB |

### Data Health (`/data-health` vs `/Data_Health`)

| App | FCP | DCL | Load | Bytes | JS req | JS bytes |
|---|---|---|---|---|---|---|
| Streamlit | 656 | 455.5 | 455.5 | 5,694,385 | 155 | 5,005,487 |
| React | 160 | 31.1 | 31.4 | 540,892 | 1 | 70,250 |
| Δ | −496 ms | −424 ms | −424 ms | −5.15 MB | −154 | −4.94 MB |

## 3. Worst-regression callout

None. The smallest React win is **Home FCP (220 ms vs 500 ms, 2.3×)**;
every other route/metric pair is a larger React win. Home is React's
slowest route because it fetches four JSON artifacts (`manifest`,
`predictions` ≈ 939 KB, `release_gate`, `model_performance`) before
first paint of the matchup list — still ~3.6× lighter than Streamlit's
smallest page load.

## 4. Reading these numbers (caveats)

1. **TTI estimate.** The harness's `tti_estimate_ms` is
   `max(DCL, load) + startTime`, *not* a true Lighthouse TTI (no 5-second
   quiet window). It is reported only as a parity-comparable analogue and
   tracks DCL/load here.
2. **What Streamlit's numbers include.** Each measurement is a fresh
   browser context, so Streamlit re-downloads its full static JS payload
   (135–172 module-preload chunks, 3.4–5.3 MB) on every route. Repeat
   real-world visits hit the HTTP cache and are cheaper than shown; the
   same applies to React's single 70 KB (gzip) bundle. The comparison is
   apples-to-apples because both sides use fresh contexts.
3. **What the numbers do not include.** Streamlit's post-load cost —
   WebSocket negotiation and the first script run that actually paints
   page content — happens *after* the measured `load` event. The parity
   harness's hydration polling (up to 30 s + 5 s settle) covers that
   separately; all eight Streamlit pages hydrated within the window.
   React's numbers *do* include its data fetches (the JSON artifacts are
   counted in transferred bytes and the content is painted by FCP).
4. **Data payload.** React's transferred bytes include the route's JSON
   (`predictions.json` ≈ 939 KB dominates Home). Streamlit ships no data
   over HTTP — its data arrives over the WebSocket as protobuf deltas,
   which `performance.getEntriesByType('resource')` does not count, so
   Streamlit's byte figures are *understated* relative to React's.
5. **Bundle diet.** The React app ships one JS bundle (223 KB minified,
   ~70 KB gzip) with no chart library (inline SVG) and no framework
   beyond React + React Router. §35's "initial app shell: fast; page
   navigation: instant" target is met: client-side route changes after
   first load perform no network requests except per-season JSON on
   season switch.

## 5. Raw data

- `perf/react.json` — per-route React metrics (this run)
- `perf/streamlit.json` — per-route Streamlit metrics (this run)
- `perf/console-errors.json` — 0 errors on both sides
