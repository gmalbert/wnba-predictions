/** TypeScript port of `utils.market_simulation.simulate_player_prop`.
 *
 * Mirrors the Python parity fixture generator
 * (`tests/build_scenario_fixtures.py`). Both use a deterministic Mulberry32
 * PRNG seeded with the same integer so the two implementations are
 * bit-comparable (within IEEE-754 rounding).
 *
 * The production Python implementation in `utils.market_simulation.py`
 * continues to use `numpy.random.default_rng(seed)` (PCG64); only the
 * fixture generator uses Mulberry32 so the TS port can match it exactly.
 */

export interface PropProjection {
  mean: number;
  sd: number;
  line: number;
  over_probability: number;
  under_probability: number;
  status: "paper_only" | "no_bet";
  reason: string | null;
}

function mulberry32(seed: number): () => number {
  let state = (seed + 0x6d2b79f5) >>> 0;
  return function () {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function standardNormals(rand: () => number): () => number {
  let cached: number | null = null;
  return function () {
    if (cached !== null) {
      const v = cached;
      cached = null;
      return v;
    }
    let u1 = 0;
    let u2 = 0;
    while (u1 === 0) u1 = rand();
    while (u2 === 0) u2 = rand();
    const mag = Math.sqrt(-2.0 * Math.log(u1));
    const z0 = mag * Math.cos(2 * Math.PI * u2);
    const z1 = mag * Math.sin(2 * Math.PI * u2);
    cached = z1;
    return z0;
  };
}

export function simulatePlayerProp(opts: {
  rate_per_minute: number;
  rate_sd: number;
  minutes_mean: number;
  minutes_sd: number;
  line: number;
  availability_probability: number;
  draws?: number;
  seed?: number;
}): PropProjection {
  const draws = opts.draws ?? 50_000;
  const seed = opts.seed ?? 42;
  const play = Math.min(Math.max(opts.availability_probability, 0), 1);

  let status: "paper_only" | "no_bet";
  let reason: string | null = null;
  if (0.05 < play && play < 0.8) {
    status = "no_bet";
    reason = "Unresolved availability materially affects minutes.";
  } else if (opts.minutes_sd >= Math.max(opts.minutes_mean * 0.35, 7)) {
    status = "no_bet";
    reason = "Minutes uncertainty is too wide for a prop decision.";
  } else {
    status = "paper_only";
  }

  const rand = mulberry32(seed);
  const norm = standardNormals(rand);
  const minutesSd = Math.max(opts.minutes_sd, 0.5);
  const rateSd = Math.max(opts.rate_sd, 0.01);

  let sum = 0;
  let sumSq = 0;
  let overCount = 0;
  for (let i = 0; i < draws; i++) {
    const active = rand() < play;
    const minutes = active
      ? Math.max(0, Math.min(50, opts.minutes_mean + minutesSd * norm()))
      : 0;
    const rate = Math.max(0, opts.rate_per_minute + rateSd * norm());
    const value = minutes * rate;
    sum += value;
    sumSq += value * value;
    if (value > opts.line) overCount++;
  }
  const mean = sum / draws;
  const sd = Math.sqrt(Math.max((sumSq - draws * mean * mean) / (draws - 1), 0));
  const overProb = overCount / draws;
  return {
    mean: round(mean, 3),
    sd: round(sd, 3),
    line: opts.line,
    over_probability: round(overProb, 4),
    under_probability: round(1 - overProb, 4),
    status,
    reason,
  };
}

function round(value: number, digits: number): number {
  const f = Math.pow(10, digits);
  return Math.round(value * f) / f;
}

/** TypeScript port of `utils.market_simulation.simulate_correlated_parlay`. */
export interface ParlayResult {
  joint_probability: number;
  independent_probability: number;
  dependence_lift: number;
  paper_only: true;
}

export function simulateCorrelatedParlay(
  legProbabilities: number[],
  correlation: number[][] | null,
  opts: { draws?: number; seed?: number } = {},
): ParlayResult {
  const draws = opts.draws ?? 100_000;
  const seed = opts.seed ?? 42;
  const n = legProbabilities.length;
  if (n === 0) {
    return {
      joint_probability: 0,
      independent_probability: 0,
      dependence_lift: 0,
      paper_only: true,
    };
  }
  const probs = legProbabilities.map((p) => Math.min(Math.max(p, 1e-6), 1 - 1e-6));
  const thresholds = probs.map((p) => inverseNormalCdf(p));

  const corr: number[][] = Array.from({ length: n }, () => new Array(n).fill(0));
  for (let i = 0; i < n; i++) corr[i][i] = 1;
  if (correlation) {
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        if (i === j) continue;
        const v = correlation[i]?.[j];
        if (typeof v === "number") corr[i][j] = v;
      }
    }
  }
  const safeCorr = nearestCorrelationMatrix(corr);

  const L = cholesky(safeCorr);

  const rand = mulberry32(seed);
  const norm = standardNormals(rand);
  let joint = 0;
  for (let i = 0; i < draws; i++) {
    const z = new Array(n).fill(0);
    for (let r = 0; r < n; r++) z[r] = norm();
    const x = new Array(n).fill(0);
    for (let r = 0; r < n; r++) {
      let v = 0;
      for (let c = 0; c <= r; c++) v += (L[r][c] ?? 0) * (z[c] ?? 0);
      x[r] = v;
    }
    let allHit = true;
    for (let r = 0; r < n; r++) {
      if ((x[r] ?? 0) > (thresholds[r] ?? 0)) {
        allHit = false;
        break;
      }
    }
    if (allHit) joint++;
  }
  const jointProb = joint / draws;
  const independent = probs.reduce((acc, p) => acc * p, 1);
  return {
    joint_probability: round(jointProb, 5),
    independent_probability: round(independent, 5),
    dependence_lift: round(jointProb - independent, 5),
    paper_only: true,
  };
}

function nearestCorrelationMatrix(matrix: number[][]): number[][] {
  const n = matrix.length;
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const a = matrix[i][j] ?? 0;
      const b = matrix[j][i] ?? 0;
      matrix[i][j] = (a + b) / 2;
    }
  }
  const { values, vectors } = jacobi(matrix, 50);
  const fixedValues = values.map((v) => Math.max(v, 1e-8));
  const reconstructed: number[][] = Array.from({ length: n }, () => new Array(n).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      let sum = 0;
      for (let k = 0; k < n; k++) sum += (vectors[i][k] ?? 0) * (fixedValues[k] ?? 0) * (vectors[j][k] ?? 0);
      reconstructed[i][j] = sum;
    }
  }
  const scales: number[] = new Array(n).fill(0);
  for (let i = 0; i < n; i++) scales[i] = Math.sqrt(Math.max(reconstructed[i][i] ?? 1, 1e-12));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      reconstructed[i][j] = reconstructed[i][j] / (scales[i] * scales[j]);
    }
  }
  return reconstructed;
}

function jacobi(matrix: number[][], maxSweeps: number): { values: number[]; vectors: number[][] } {
  const n = matrix.length;
  const a = matrix.map((row) => row.slice());
  const v: number[][] = Array.from({ length: n }, (_, i) => {
    const row = new Array(n).fill(0);
    row[i] = 1;
    return row;
  });
  for (let sweep = 0; sweep < maxSweeps; sweep++) {
    let off = 0;
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) off += Math.abs(a[i][j] ?? 0);
    }
    if (off < 1e-14) break;
    for (let p = 0; p < n; p++) {
      for (let q = p + 1; q < n; q++) {
        const apq = a[p][q] ?? 0;
        if (Math.abs(apq) < 1e-20) continue;
        const app = a[p][p] ?? 0;
        const aqq = a[q][q] ?? 0;
        const theta = (aqq - app) / (2 * apq);
        const t = theta >= 0
          ? 1 / (theta + Math.sqrt(1 + theta * theta))
          : 1 / (theta - Math.sqrt(1 + theta * theta));
        const c = 1 / Math.sqrt(1 + t * t);
        const s = t * c;
        a[p][p] = app - t * apq;
        a[q][q] = aqq + t * apq;
        a[p][q] = 0;
        a[q][p] = 0;
        for (let i = 0; i < n; i++) {
          if (i === p || i === q) continue;
          const aip = a[i][p] ?? 0;
          const aiq = a[i][q] ?? 0;
          a[i][p] = c * aip - s * aiq;
          a[p][i] = a[i][p];
          a[i][q] = s * aip + c * aiq;
          a[q][i] = a[i][q];
        }
        for (let i = 0; i < n; i++) {
          const vip = v[i][p] ?? 0;
          const viq = v[i][q] ?? 0;
          v[i][p] = c * vip - s * viq;
          v[i][q] = s * vip + c * viq;
        }
      }
    }
  }
  const values = a.map((row, i) => row[i] ?? 0);
  return { values, vectors: v };
}

function cholesky(matrix: number[][]): number[][] {
  const n = matrix.length;
  const L: number[][] = Array.from({ length: n }, () => new Array(n).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j <= i; j++) {
      let sum = 0;
      for (let k = 0; k < j; k++) sum += (L[i][k] ?? 0) * (L[j][k] ?? 0);
      if (i === j) {
        L[i][j] = Math.sqrt(Math.max((matrix[i][i] ?? 1) - sum, 1e-12));
      } else {
        L[i][j] = ((matrix[i][j] ?? 0) - sum) / (L[j][j] || 1e-12);
      }
    }
  }
  return L;
}

function inverseNormalCdf(p: number): number {
  if (p <= 0) return -8;
  if (p >= 1) return 8;
  const a = [
    -3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
    1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00,
  ];
  const b = [
    -5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
    6.680131188771972e+01, -1.328068155288572e+01,
  ];
  const c = [
    -7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
    -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00,
  ];
  const d = [
    7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
    3.754408661907416e+00,
  ];
  const plow = 0.02425;
  const phigh = 1 - plow;
  let q: number, r: number;
  if (p < plow) {
    q = Math.sqrt(-2 * Math.log(p));
    return (
      (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    );
  } else if (p <= phigh) {
    q = p - 0.5;
    r = q * q;
    return (
      ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) /
      (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    );
  } else {
    q = Math.sqrt(-2 * Math.log(1 - p));
    return (
      -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    );
  }
}

export function stakingPolicy(releaseGatePassed: boolean): {
  live_stake_units: number;
  paper_stake_units: number;
  kelly_enabled: false;
  reason: string;
} {
  return {
    live_stake_units: 0,
    paper_stake_units: 1,
    kelly_enabled: false,
    reason: releaseGatePassed
      ? "Production gate passed, but Kelly remains disabled until a separate staking review."
      : "Production release gate is closed.",
  };
}

/** TypeScript port of `utils.scenario_engine.build_margin_scenarios` +
 *  `summarize_margin_scenarios` + `mixture_prediction`.
 */
export interface RotationRow {
  canonical_team_id: number | string | null;
  availability_probability: number;
  minutes_mean_if_active: number;
  minutes_sd_if_active: number;
  impact_per_minute: number;
}

export interface MarginScenarioSummary {
  margin_mean: number;
  margin_sd: number;
  scenario_uncertainty: number;
  scenarios: number;
}

export function mixturePrediction(
  scenarios: Array<[number, number, number]>,
): [number, number] {
  if (scenarios.length === 0) return [0, 0];
  const weights = scenarios.map((s) => Math.max(s[0], 0));
  const total = weights.reduce((a, b) => a + b, 0);
  const norm = total <= 0
    ? new Array(scenarios.length).fill(1 / scenarios.length)
    : weights.map((w) => w / total);
  const means = scenarios.map((s) => s[1]);
  const sds = scenarios.map((s) => Math.max(s[2], 0));
  const mean = norm.reduce((acc, w, i) => acc + w * (means[i] ?? 0), 0);
  const second = norm.reduce((acc, w, i) => acc + w * ((sds[i] ?? 0) ** 2 + (means[i] ?? 0) ** 2), 0);
  return [mean, Math.sqrt(Math.max(second - mean * mean, 0))];
}

export function summarizeMarginScenarios(
  scenarios: Array<[number, number, number]>,
): MarginScenarioSummary {
  const [mean, sd] = mixturePrediction(scenarios);
  const norm = (() => {
    const weights = scenarios.map((s) => Math.max(s[0], 0));
    const total = weights.reduce((a, b) => a + b, 0);
    if (total <= 0) return new Array(scenarios.length).fill(1 / scenarios.length);
    return weights.map((w) => w / total);
  })();
  let within = 0;
  for (let i = 0; i < scenarios.length; i++) {
    within += (norm[i] ?? 0) * (scenarios[i]?.[2] ?? 0) ** 2;
  }
  const between = Math.sqrt(Math.max(sd * sd - within, 0));
  return {
    margin_mean: round(mean, 3),
    margin_sd: round(sd, 3),
    scenario_uncertainty: round(between, 3),
    scenarios: scenarios.length,
  };
}

export function buildMarginScenarios(
  baseMargin: number,
  baseSd: number,
  rotation: RotationRow[],
  homeTeamId: number | string,
  awayTeamId: number | string,
  maxUncertain: number = 4,
): Array<[number, number, number]> {
  if (!rotation || rotation.length === 0) {
    return [[1, baseMargin, baseSd]];
  }
  const relevant = rotation.filter((r) =>
    String(r.canonical_team_id) === String(homeTeamId) ||
    String(r.canonical_team_id) === String(awayTeamId),
  );
  const scored = relevant.map((r) => ({
    r,
    uncertainty:
      r.availability_probability *
      (1 - r.availability_probability) *
      r.minutes_mean_if_active *
      Math.abs(r.impact_per_minute),
  }));
  const uncertain = scored
    .filter((s) => s.r.availability_probability >= 0.05 && s.r.availability_probability <= 0.95)
    .sort((a, b) => b.uncertainty - a.uncertainty)
    .slice(0, maxUncertain);
  if (uncertain.length === 0) {
    return [[1, baseMargin, baseSd]];
  }
  const scenarios: Array<[number, number, number]> = [];
  const statesCount = 1 << uncertain.length;
  for (let mask = 0; mask < statesCount; mask++) {
    let weight = 1;
    let margin = baseMargin;
    for (let i = 0; i < uncertain.length; i++) {
      const state = (mask >> i) & 1;
      const player = uncertain[i].r;
      const playProb = player.availability_probability;
      weight *= state === 1 ? playProb : 1 - playProb;
      if (state === 0) {
        const impact = player.minutes_mean_if_active * player.impact_per_minute;
        if (String(player.canonical_team_id) === String(homeTeamId)) {
          margin -= impact;
        } else {
          margin += impact;
        }
      }
    }
    scenarios.push([weight, margin, baseSd]);
  }
  return scenarios;
}