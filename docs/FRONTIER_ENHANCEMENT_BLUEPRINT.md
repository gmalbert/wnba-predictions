# Frontier Enhancement Blueprint

The existing port plan, migration guide, implementation checklist, file-disposition matrix, adapters, contracts, and reference-data bootstrap establish a strong foundation. The next roadmap should remain WNBA-specific rather than merely inheriting NBA defaults.

## Minutes and lineup hierarchy

Model player minutes as distributions conditioned on availability, role, rotation, rest, score context, and recent return. Learn player and lineup effects with partial pooling because the league's smaller rotations create high leverage but sparse combinations.

```python
def mixture_prediction(scenarios):
    # scenarios: [(probability, margin_mean, margin_sd), ...]
    mean = sum(w * m for w, m, _ in scenarios)
    second = sum(w * (s*s + m*m) for w, m, s in scenarios)
    return mean, np.sqrt(max(second - mean*mean, 0))
```

## WNBA-specific data

- Overseas-season minutes, travel, return dates, and rest (carefully sourced).
- Commissioner’s Cup, compact scheduling, cross-country travel, and early starts.
- Player availability/news observation history and confirmed starters.
- On/off possessions, lineup minutes, play-by-play, referee crews, and tracking features where available.
- Expansion drafts/teams and rookies with hierarchical cold-start priors.
- Timestamped game/prop odds across books.

## Product additions

- Rotation and availability scenario editor.
- Travel/workload timeline including overseas context where verified.
- Commissioner’s Cup/playoff context labels without assuming motivation effects.
- Lineup matchup and minutes-uncertainty views.
- Source-health panel driven by the existing adapter metadata.
- Accessible no-bet state for unresolved star availability.

## Operations and evaluation

Preserve the adapter boundary and add contract fixtures for partial schedules, postponements, neutral sites, expansion teams, and missing player IDs. Replay at morning, injury-report, and pre-tip horizons. Report log loss, calibration, CRPS/MAE, CLV, and performance by travel, rest, roster continuity, season phase, and data source. Compare with market, Elo, and simple efficiency baselines; abstain when scenario uncertainty dominates the apparent edge.
