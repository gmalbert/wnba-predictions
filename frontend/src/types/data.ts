/** Shared TypeScript types matching `docs/react-migration/01_DATA_CONTRACT.md`. */

export type Confidence = "High" | "Medium" | "Low";
export type ReleaseGateStatus = "production_ready" | "limited_paper" | "shadow_only" | "missing";
export type ManifestStatus = "ok" | "degraded" | "failed";

export interface Manifest {
  schema_version: number;
  generated_at: string;
  league_key: string;
  sport: string;
  season: number;
  model_version: string;
  feature_schema_version: string;
  release_mode: "paper_only" | "production";
  status: ManifestStatus;
  artifacts: Record<string, string>;
  thresholds: {
    predictions_stale_hours: number;
    standings_stale_hours: number;
    team_stats_stale_hours: number;
    model_perf_stale_hours: number;
  };
}

export interface PredictionTravelContext {
  home: Record<string, unknown>;
  away: Record<string, unknown>;
  labels: string[];
}

export interface PredictionAvailability {
  canonical_player_id: number | null;
  canonical_team_id: number | null;
  player_name?: string;
  role?: string;
  status?: string;
  confirmed_starter?: boolean;
  availability_probability?: number;
  minutes_mean_if_active?: number;
  minutes_sd_if_active?: number;
  impact_per_minute?: number;
}

export interface PredictionLineupRow {
  side: "home" | "away";
  rank: number;
  player_id: string;
  player: string;
  minutes_mean: number;
  minutes_sd: number;
  role?: string;
  status?: string;
  net_rating?: number | null;
}

export interface PredictionGame {
  prediction_id: string;
  game_id: string;
  season: number;
  game_date: string;
  scheduled_start: string;
  home_team: string;
  away_team: string;
  home_team_id: number | null;
  away_team_id: number | null;
  home_win_prob: number | null;
  away_win_prob: number | null;
  predicted_spread: number | null;
  predicted_total: number | null;
  margin_mean: number | null;
  margin_sd: number | null;
  margin_low: number | null;
  margin_high: number | null;
  total_mean: number | null;
  total_sd: number | null;
  total_low: number | null;
  total_high: number | null;
  market_home_prob: number | null;
  market_spread: number | null;
  market_total: number | null;
  edge: number | null;
  confidence: Confidence;
  status: string;
  no_bet_reason: string | null;
  paper_only: boolean;
  release_gate_status: ReleaseGateStatus | string | null;
  scenario_uncertainty: number | null;
  availability_status: string | null;
  roster_continuity_home: number | null;
  roster_continuity_away: number | null;
  travel_context: PredictionTravelContext;
  availability: PredictionAvailability[];
  lineup_matchup: PredictionLineupRow[];
  model_version: string | null;
  feature_schema_version: string | null;
  generated_at: string | null;
  stage: string | null;
}

export interface PredictionsPayload {
  schema_version: number;
  generated_at: string;
  league_key: string;
  games: PredictionGame[];
}

export interface StandingsRow {
  team_id: number | null;
  team: string;
  nickname?: string | null;
  city: string;
  wins: number | null;
  losses: number | null;
  win_pct: number | null;
  conference: string | null;
  playoff_rank: number | null;
  streak: string | null;
  home_record: string | null;
  road_record: string | null;
  l10: string | null;
  points_per_game: number | null;
  opp_points_per_game: number | null;
  point_diff: number | null;
  games_back: number | null;
}

export interface StandingsPayload {
  schema_version: number;
  generated_at: string;
  league_key: string;
  season: number;
  seasons_available: number[];
  rows: StandingsRow[];
}

export interface TeamGameSummary {
  game_date: string | null;
  opponent_team_id: number | null;
  is_home: number | null;
  points: number | null;
  win: number | null;
}

export interface TeamTrendPoint {
  game_date: string | null;
  points: number | null;
  points_L10: number | null;
}

export interface TeamEntry {
  team_id: number | null;
  name: string;
  summary: {
    games: number | null;
    win_pct_L10: number | null;
    points_L10: number | null;
    rest_days: number | null;
    streak: number | null;
  };
  recent_games: TeamGameSummary[];
  trends: TeamTrendPoint[];
  rankings: Record<string, number>;
}

export interface TeamStatsPayload {
  schema_version: number;
  generated_at: string;
  league_key: string;
  season: number;
  seasons_available: number[];
  teams: Record<string, TeamEntry>;
}

export interface PlayerGameSummary {
  game_date: string | null;
  points: number | null;
  rebounds: number | null;
  assists: number | null;
  minutes: number | null;
  points_per40: number | null;
}

export interface PlayerTrendPoint {
  game_date: string | null;
  points: number | null;
}

export interface PlayerEntry {
  player_id: number | null;
  name: string;
  team_id: number | null;
  summary: {
    games: number | null;
    ppg: number | null;
    ppg_per40_L10: number | null;
    rpg_per40_L10: number | null;
    apg_per40_L10: number | null;
  };
  recent_games: PlayerGameSummary[];
  trends?: PlayerTrendPoint[];
}

export interface PlayerStatsPayload {
  schema_version: number;
  generated_at: string;
  league_key: string;
  season: number;
  seasons_available: number[];
  players: Record<string, PlayerEntry>;
}

export interface ModelPerformancePayload {
  schema_version: number;
  generated_at: string;
  league_key: string;
  artifact_status: string | null;
  release_gate: {
    status: string;
    passed: boolean;
    paper_only: boolean;
    checks: Record<string, boolean>;
    holdout_season: number | null;
    holdout_rows: number;
    priced_bets: number;
    mean_clv: number | null;
    drift_suspended: boolean;
  };
  win_model: {
    accuracy: number | null;
    log_loss: number | null;
    brier_score: number | null;
    n_test: number | null;
  };
  winner_calibration: {
    ece: number | null;
    mce: number | null;
    bins: Array<{
      lower: number;
      upper: number;
      n: number;
      mean_probability: number;
      observed_rate: number;
      absolute_error: number;
    }>;
  };
  walk_forward: Array<{
    accuracy: number;
    log_loss: number;
    brier_score: number;
    train_through: number;
    test_season: number;
    n_train: number;
    n_test: number;
  }>;
  baselines: Record<string, Record<string, number>>;
  line_bucket_calibration: {
    spread: unknown[];
    total: unknown[];
  };
  paper_ledger: {
    priced_bets: number;
    graded_bets: number;
    mean_clv: number | null;
    roi: number | null;
    profit_units: number;
    by_market: Array<Record<string, unknown>>;
  };
  ledger: Array<Record<string, unknown>>;
  drift: {
    max_psi: number;
    warning_features: string[];
    suspended: boolean;
  };
  segment_performance: Record<string, Array<Record<string, unknown>>>;
  margin: Record<string, number | null>;
  totals: Record<string, number | null>;
  seasons: number[];
  n_rows: number;
  holdout_season: number | null;
  holdout_rows: number;
  holdout_2025?: {
    margin_distribution?: Record<string, number | null>;
    total_distribution?: Record<string, number | null>;
    winner_calibration?: ModelPerformancePayload["winner_calibration"];
  };
}

export interface DataHealthSource {
  source: string;
  data_type: string;
  ok: boolean;
  last_attempt: string | null;
  last_success: string | null;
  error: string | null;
  records: number;
}

export interface DataHealthPayload {
  schema_version: number;
  generated_at: string;
  league_key: string;
  sources: DataHealthSource[];
  capability_registry: Array<{
    data_type: string;
    priority: number;
    source: string;
  }>;
  artifact_safety: {
    league: string;
    season: number;
    schema: string;
    artifact: string;
  };
  as_of_coverage: Array<{
    dataset: string;
    required_history: string;
    policy: string;
  }>;
}

export interface ReleaseGatePayload {
  schema_version: number;
  generated_at: string;
  league_key: string;
  status: ReleaseGateStatus;
  passed: boolean;
  paper_only: boolean;
  checks: Record<string, boolean>;
  holdout_season: number | null;
  holdout_rows: number;
  priced_bets: number;
  mean_clv: number | null;
  drift_suspended: boolean;
}

export interface ScenarioPolicyPayload {
  schema_version: number;
  generated_at: string;
  league_key: string;
  release_gate_passed: boolean;
  live_stake_units: number;
  paper_stake_units: number;
  kelly_enabled: boolean;
  reason: string;
}

export interface Envelope<T> {
  schema_version: number;
  generated_at: string;
  league_key: string;
}