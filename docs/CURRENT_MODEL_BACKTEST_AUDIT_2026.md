# Current-model backtest audit (2026)

## Verdict

The current artifact was trained/evaluated only on 2018-2022 (1,041 rows), despite deployment in 2026. Its aggregate winner metrics are 62.20% accuracy, 0.6651 log loss, and 0.2348 Brier. Five walk-forward folds average about 60.35% accuracy, 0.6806 log loss, and 0.2411 Brier, with large fold variation (52.6%-69.9% accuracy). Margin MAE/RMSE are 4.78/6.33 points; total-points MAE/RMSE are 6.78/10.49. No 2023-25 validation, market baseline, frozen bet ledger, CLV, or ROI exists.

## Changes justified by the result

1. Do not treat the old artifact as production-ready. Backfill 2023-25 and hold out 2025 before judging 2026 use.
2. Use expanding-season folds and recency weighting; WNBA roster, schedule, expansion, and style changes make stale training risky.
3. Calibrate winner, margin, and total distributions separately. Compare to de-vigged moneyline/spread/total closes.
4. Add player availability/minutes, travel/rest, Commissioner’s Cup/playoff context, lineup continuity, and pace/shot-quality features with as-of timestamps.

## Betting strategy decision

- **Moneyline:** no live use until recent-season replay.
- **Spread:** 4.78 margin MAE is descriptive, not ATS proof.
- **Totals/team totals:** 6.78 MAE requires line-bucket calibration and real prices.
- **Player props:** require minutes uncertainty and confirmed availability.
- **Parlays/futures:** simulate dependence and roster uncertainty.
- **Staking:** paper-only; no Kelly.

## Release gate

Untouched 2025 season and forward 2026 shadow ledger, market-relative scoring, 300+ priced bets, positive CLV, and drift checks that automatically suspend stale artifacts.
