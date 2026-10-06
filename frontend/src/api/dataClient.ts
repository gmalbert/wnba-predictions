/** Single configurable data client for the React frontend.
 *
 * In development the JSON artifacts live under `/data/` (Vite serves anything
 * under `public/` from the site root). In production they sit next to the
 * static bundle. The optional `VITE_DATA_BASE_URL` env var overrides the
 * default. No component should ever read raw URLs.
 */

const DEFAULT_BASE_URL = "/data/";

function resolveBaseUrl(): string {
  const envBase = import.meta.env.VITE_DATA_BASE_URL;
  if (envBase && envBase.length > 0) {
    return envBase.endsWith("/") ? envBase : envBase + "/";
  }
  return DEFAULT_BASE_URL;
}

const BASE_URL = resolveBaseUrl();

function url(name: string): string {
  return `${BASE_URL}${name}`;
}

export class DataError extends Error {
  constructor(message: string, public cause?: unknown) {
    super(message);
    this.name = "DataError";
  }
}

async function fetchJson<T>(name: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url(name), init);
  if (!response.ok) {
    throw new DataError(
      `Failed to fetch ${name} (${response.status} ${response.statusText})`,
    );
  }
  try {
    return (await response.json()) as T;
  } catch (err) {
    throw new DataError(`Failed to parse JSON for ${name}`, err);
  }
}

export const dataClient = {
  baseUrl: BASE_URL,
  url,
  fetchJson,
};

export async function fetchManifest() {
  return fetchJson<import("../types/data").Manifest>("manifest.json");
}
export async function fetchPredictions() {
  return fetchJson<import("../types/data").PredictionsPayload>("predictions.json");
}
export async function fetchStandings(season?: number) {
  if (season === undefined) {
    return fetchJson<import("../types/data").StandingsPayload>("standings.json");
  }
  return fetchJson<import("../types/data").StandingsPayload>(`standings_${season}.json`);
}
export async function fetchTeamStats(season?: number) {
  if (season === undefined) {
    return fetchJson<import("../types/data").TeamStatsPayload>("team_stats.json");
  }
  return fetchJson<import("../types/data").TeamStatsPayload>(`team_stats_${season}.json`);
}
export async function fetchPlayerStats(season?: number) {
  if (season === undefined) {
    return fetchJson<import("../types/data").PlayerStatsPayload>("player_stats.json");
  }
  return fetchJson<import("../types/data").PlayerStatsPayload>(`player_stats_${season}.json`);
}
export async function fetchModelPerformance() {
  return fetchJson<import("../types/data").ModelPerformancePayload>("model_performance.json");
}
export async function fetchDataHealth() {
  return fetchJson<import("../types/data").DataHealthPayload>("data_health.json");
}
export async function fetchReleaseGate() {
  return fetchJson<import("../types/data").ReleaseGatePayload>("release_gate.json");
}
export async function fetchScenarioPolicy() {
  return fetchJson<import("../types/data").ScenarioPolicyPayload>("scenario_policy.json");
}