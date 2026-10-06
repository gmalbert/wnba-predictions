/** Parity test for the TypeScript port of `utils.market_simulation`.
 *
 * Loads `tests/fixtures/scenario_lab_parity.json` (produced by
 * `tests/build_scenario_fixtures.py` from the canonical Python pipeline) and
 * compares each case's output against the TS implementation.
 *
 * Run with: npx tsx tests/test_scenario_parity.ts
 */

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { simulateCorrelatedParlay, simulatePlayerProp } from "../src/utils/scenario";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

interface PropFixture {
  kind: "player_prop";
  name: string;
  input: {
    rate_per_minute: number;
    rate_sd: number;
    minutes_mean: number;
    minutes_sd: number;
    availability_probability: number;
    line: number;
  };
  expected: {
    mean: number;
    sd: number;
    over_probability: number;
    under_probability: number;
    status: "paper_only" | "no_bet";
    reason: string | null;
  };
  tolerance: number;
}

interface ParlayFixture {
  kind: "parlay";
  name: string;
  input: { leg_probabilities: number[]; correlation: number };
  expected: {
    joint_probability: number;
    independent_probability: number;
    dependence_lift: number;
  };
  tolerance: number;
}

type Fixture = PropFixture | ParlayFixture;

function loadFixtures(): Fixture[] {
  const path = resolve(__dirname, "..", "..", "tests", "fixtures", "scenario_lab_parity.json");
  return JSON.parse(readFileSync(path, "utf-8")) as Fixture[];
}

function within(actual: number, expected: number, tol: number): boolean {
  return Math.abs(actual - expected) <= tol;
}

function run(): number {
  const fixtures = loadFixtures();
  let failed = 0;
  for (const fixture of fixtures) {
    if (fixture.kind === "player_prop") {
      const proj = simulatePlayerProp({
        rate_per_minute: fixture.input.rate_per_minute,
        rate_sd: fixture.input.rate_sd,
        minutes_mean: fixture.input.minutes_mean,
        minutes_sd: fixture.input.minutes_sd,
        line: fixture.input.line,
        availability_probability: fixture.input.availability_probability,
      });
      const checks: Array<[string, number, number]> = [
        ["mean", proj.mean, fixture.expected.mean],
        ["sd", proj.sd, fixture.expected.sd],
        ["over_probability", proj.over_probability, fixture.expected.over_probability],
        ["under_probability", proj.under_probability, fixture.expected.under_probability],
      ];
      const statusMatch = proj.status === fixture.expected.status;
      const reasonMatch = proj.reason === fixture.expected.reason;
      for (const [label, actual, expected] of checks) {
        const ok = within(actual, expected, fixture.tolerance);
        if (!ok) {
          failed++;
          console.error(
            `[FAIL] ${fixture.name} ${label}: expected=${expected} actual=${actual} tol=${fixture.tolerance}`,
          );
        }
      }
      if (!statusMatch) {
        failed++;
        console.error(
          `[FAIL] ${fixture.name} status: expected=${fixture.expected.status} actual=${proj.status}`,
        );
      }
      if (!reasonMatch) {
        failed++;
        console.error(
          `[FAIL] ${fixture.name} reason: expected=${fixture.expected.reason} actual=${proj.reason}`,
        );
      }
      if (statusMatch && reasonMatch && checks.every((c) => within(c[1], c[2], fixture.tolerance))) {
        console.log(`[ OK ] ${fixture.name}`);
      }
    } else {
      const n = fixture.input.leg_probabilities.length;
      const corr = fixture.input.correlation;
      const matrix = Array.from({ length: n }, (_, i) =>
        Array.from({ length: n }, (_, j) => (i === j ? 1 : corr)),
      );
      const result = simulateCorrelatedParlay(fixture.input.leg_probabilities, matrix);
      const checks: Array<[string, number, number]> = [
        ["joint_probability", result.joint_probability, fixture.expected.joint_probability],
        ["independent_probability", result.independent_probability, fixture.expected.independent_probability],
        ["dependence_lift", result.dependence_lift, fixture.expected.dependence_lift],
      ];
      for (const [label, actual, expected] of checks) {
        const ok = within(actual, expected, fixture.tolerance);
        if (!ok) {
          failed++;
          console.error(
            `[FAIL] ${fixture.name} ${label}: expected=${expected} actual=${actual} tol=${fixture.tolerance}`,
          );
        }
      }
      if (checks.every((c) => within(c[1], c[2], fixture.tolerance))) {
        console.log(`[ OK ] ${fixture.name}`);
      }
    }
  }
  if (failed === 0) {
    console.log(`All ${fixtures.length} parity fixtures pass within tolerance.`);
    return 0;
  }
  console.error(`${failed} parity check(s) failed.`);
  return 1;
}

process.exit(run());