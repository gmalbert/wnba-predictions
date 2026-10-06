"""Validate the JSON artifacts produced by ``scripts/export_web_data.py``.

The validator is the second half of the React/frontend contract: it is run
in CI and fails the build if any required artifact is missing, malformed,
or has grown beyond its size budget. It never touches the upstream
parquet; it only inspects the JSON it ships to the browser.

Run::

    python scripts/validate_web_data.py frontend/public/data
    python scripts/validate_web_data.py frontend/public/data --strict

Exit code is 0 on success, 1 on any failure. ``--strict`` additionally
treats size warnings as failures.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


# Target budgets from docs/react-migration/01_DATA_CONTRACT.md §Size budgets
SIZE_BUDGETS_BYTES: dict[str, int] = {
    "manifest.json": 25 * 1024,
    "predictions.json": 1 * 1024 * 1024,
    "standings.json": 500 * 1024,
    "team_stats.json": 5 * 1024 * 1024,
    "player_stats.json": 5 * 1024 * 1024,
    "model_performance.json": 2 * 1024 * 1024,
    "data_health.json": 500 * 1024,
    "release_gate.json": 50 * 1024,
    "scenario_policy.json": 10 * 1024,
}

REQUIRED_ARTIFACTS = list(SIZE_BUDGETS_BYTES.keys())

FORBIDDEN_KEYS = {
    "ODDS_API_IO_KEY",
    "THERUNDOWN_API_KEY",
    "ODDS_API_KEY",
    "NBA_API_KEY",
    "BALLDONTLIE_TOKEN",
    "OPENAI_API_KEY",
}

EXPECTED_SCHEMA_VERSIONS = {
    "manifest.json": 1,
    "predictions.json": 1,
    "standings.json": 1,
    "team_stats.json": 1,
    "player_stats.json": 1,
    "model_performance.json": 1,
    "data_health.json": 1,
    "release_gate.json": 1,
    "scenario_policy.json": 1,
}


def _walk(value: Any, path: str, callback) -> None:
    """Yield every scalar value in ``value`` to ``callback(path, v)``."""
    if isinstance(value, dict):
        for k, v in value.items():
            _walk(v, f"{path}.{k}" if path else str(k), callback)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _walk(v, f"{path}[{i}]", callback)
    else:
        callback(path, value)


def _check_scalar(path: str, value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            issues.append(f"{path}: contains NaN/Infinity")
    elif isinstance(value, str):
        if len(value) > 12 and "T" in value and value.endswith("Z") and value[:-1].replace("-", "").replace(":", "").replace(".", "").replace("T", "").isdigit():
            pass
    return issues


def _check_timestamp_format(path: str, value: Any) -> list[str]:
    if not isinstance(value, str):
        return [f"{path}: expected ISO-8601 string, got {type(value).__name__}"]
    if not value:
        return []
    if not (value.endswith("Z") or "+" in value[10:]):
        return [f"{path}: timestamp '{value}' is not ISO-8601 UTC"]
    return []


def validate_artifact(path: Path) -> tuple[bool, list[str], list[str]]:
    """Validate one JSON artifact. Returns (ok, errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return False, [f"missing required artifact: {path.name}"], []

    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return False, [f"{path.name}: file is empty"], []

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return False, [f"{path.name}: invalid JSON ({exc.msg} at line {exc.lineno} col {exc.colno})"], []

    if not isinstance(payload, dict):
        return False, [f"{path.name}: top-level must be an object"], []

    schema_version = payload.get("schema_version")
    expected = EXPECTED_SCHEMA_VERSIONS.get(path.name)
    if expected is not None and schema_version != expected:
        errors.append(f"{path.name}: schema_version={schema_version!r}, expected {expected}")

    league_key = payload.get("league_key")
    if league_key != "wnba":
        errors.append(f"{path.name}: league_key={league_key!r}, expected 'wnba'")

    generated_at = payload.get("generated_at")
    if not generated_at:
        warnings.append(f"{path.name}: generated_at missing")
    else:
        for issue in _check_timestamp_format(f"{path.name}.generated_at", generated_at):
            errors.append(issue)

    issues_found: list[str] = []
    _walk(payload, "", lambda p, v: issues_found.extend(_check_scalar(p, v)))
    errors.extend(issues_found)

    forbidden = []
    _walk(payload, "", lambda p, v: forbidden.extend(FORBIDDEN_KEYS & {str(v)}) if isinstance(v, str) else None)
    if forbidden:
        errors.append(f"{path.name}: contains forbidden secret-like key(s): {sorted(set(forbidden))}")

    size = path.stat().st_size
    budget = SIZE_BUDGETS_BYTES.get(path.name)
    if budget and size > budget:
        if size > budget * 1.5:
            errors.append(
                f"{path.name}: size {size / 1024:.1f} KB exceeds budget "
                f"{budget / 1024:.1f} KB (>50% over)"
            )
        else:
            warnings.append(
                f"{path.name}: size {size / 1024:.1f} KB exceeds target "
                f"{budget / 1024:.1f} KB"
            )

    return (len(errors) == 0), errors, warnings


def validate_predictions(path: Path, payload: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    games = payload.get("games", [])
    if not isinstance(games, list):
        return False, [f"{path.name}: games must be a list"], []
    for i, game in enumerate(games):
        if not isinstance(game, dict):
            errors.append(f"{path.name}.games[{i}]: not an object")
            continue
        home = game.get("home_win_prob")
        away = game.get("away_win_prob")
        if home is not None and away is not None:
            total = float(home) + float(away)
            if abs(total - 1.0) > 1e-6:
                warnings.append(
                    f"{path.name}.games[{i}]: home_win_prob + away_win_prob = {total:.6f} (drift)"
                )
        for required in ("prediction_id", "game_id", "home_team", "away_team"):
            if game.get(required) in (None, ""):
                errors.append(f"{path.name}.games[{i}]: missing required field {required}")
    return (len(errors) == 0), errors, warnings


def validate_release_gate(path: Path, payload: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("status") not in {"production_ready", "limited_paper", "shadow_only", "missing"}:
        errors.append(f"{path.name}: invalid status {payload.get('status')!r}")
    if not isinstance(payload.get("checks", {}), dict):
        errors.append(f"{path.name}: checks must be an object")
    return (len(errors) == 0), errors, warnings


def validate_data_health(path: Path, payload: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    sources = payload.get("sources", [])
    if not isinstance(sources, list):
        errors.append(f"{path.name}: sources must be a list")
    capability = payload.get("capability_registry", [])
    if not isinstance(capability, list):
        errors.append(f"{path.name}: capability_registry must be a list")
    artifact = payload.get("artifact_safety", {})
    if not isinstance(artifact, dict) or not artifact.get("league"):
        errors.append(f"{path.name}: artifact_safety must include league")
    return (len(errors) == 0), errors, warnings


def validate_manifest(path: Path, payload: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append(f"{path.name}: artifacts must be an object")
    else:
        expected_keys = {
            "predictions", "standings", "team_stats", "player_stats",
            "model_performance", "data_health", "release_gate", "scenario_policy",
        }
        for key in expected_keys:
            if key not in artifacts:
                errors.append(f"{path.name}: artifacts map missing '{key}'")
        for value in artifacts.values():
            if value not in REQUIRED_ARTIFACTS:
                errors.append(f"{path.name}: artifacts map references unknown file '{value}'")
    return (len(errors) == 0), errors, warnings


SPECIFIC_VALIDATORS = {
    "manifest.json": validate_manifest,
    "predictions.json": validate_predictions,
    "release_gate.json": validate_release_gate,
    "data_health.json": validate_data_health,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate exported web JSON artifacts.")
    parser.add_argument("path", nargs="?", default="frontend/public/data")
    parser.add_argument("--strict", action="store_true", help="Treat size warnings as failures")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"ERROR: data directory {root} does not exist", file=sys.stderr)
        return 1

    total_errors = 0
    total_warnings = 0
    print(f"Validating web artifacts under {root}")
    for name in REQUIRED_ARTIFACTS:
        path = root / name
        ok, errors, warnings = validate_artifact(path)
        if SPECIFIC_VALIDATORS.get(name):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
            extra_ok, extra_errors, extra_warnings = SPECIFIC_VALIDATORS[name](path, payload)
            ok = ok and extra_ok
            errors.extend(extra_errors)
            warnings.extend(extra_warnings)
        for warning in warnings:
            total_warnings += 1
            if args.strict:
                errors.append(warning)
        for error in errors:
            total_errors += 1
            print(f"  [FAIL] {name}: {error}")
        for warning in warnings:
            print(f"  [WARN] {name}: {warning}")
        if ok and not warnings:
            print(f"  [ OK ] {name}")
    if total_errors == 0 and total_warnings == 0:
        print("All artifacts valid.")
    elif total_errors == 0:
        print(f"All artifacts valid with {total_warnings} warning(s).")
    else:
        print(f"{total_errors} error(s), {total_warnings} warning(s).")
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())