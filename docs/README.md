# WNBA Predictions Port Planning Package

This package is a repository-specific planning and migration set for converting
`gmalbert/nba-predictions` into an independent WNBA predictions application.

## Core planning

1. `WNBA_PORT_MASTER_PLAN.md` — architecture, modeling, operations, enhancements, and phased delivery.
2. `WNBA_DATA_SOURCE_AUDIT.md` — source-by-source validation, endpoint auditing, and fallback policy.
3. `WNBA_IMPLEMENTATION_CHECKLIST.md` — milestone checklist and release gates.

## Frontier audit and implementation

- `CURRENT_MODEL_BACKTEST_AUDIT_2026.md` - recent-season audit, betting policy, and production release gate.
- `FRONTIER_ENHANCEMENT_BLUEPRINT.md` - WNBA-specific data, product, modeling, and evaluation requirements.
- `FRONTIER_IMPLEMENTATION_STATUS.md` - implementation map, current release state, and verification commands.

## Transition and execution

4. `WNBA_REPOSITORY_MIGRATION_GUIDE.md` — detailed transition procedure, file-by-file actions, commit sequence, rollback points, and acceptance tests.
5. `WNBA_FILE_DISPOSITION_MATRIX.md` — explicit keep/refactor/replace/delete decision for major repository files.
6. `WNBA_EXECUTION_RUNBOOK.md` — operational sequence for implementation, data backfill, training, automation, monitoring, and production release.
