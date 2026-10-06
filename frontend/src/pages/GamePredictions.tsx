import React, { useCallback, useMemo, useState } from "react";
import { fetchPredictions } from "../api/dataClient";
import { ConfidenceBadge, NoBetBadge } from "../components/ConfidenceBadge";
import { DataFrame, Column } from "../components/DataFrame";
import { MetricCard } from "../components/MetricCard";
import { ProbabilityBar } from "../components/ProbabilityBar";
import { StatusBanner } from "../components/StatusBanner";
import { useJson } from "../hooks/useJson";
import { PredictionGame, PredictionsPayload } from "../types/data";
import {
  formatGameTime,
  num,
  pct,
  signed,
} from "../utils/format";
import { buildMarginScenarios, summarizeMarginScenarios } from "../utils/scenario";

const TABS = ["Rotation scenario", "Lineup matchup", "Travel & context", "Provenance"] as const;

export function GamePredictions() {
  const { data, loading, error } = useJson<PredictionsPayload>(
    useCallback(() => fetchPredictions(), []),
  );
  return (
    <div>
      <h1>🏀 Game Predictions</h1>
      <p className="bo-page-caption">
        Probabilistic projections with as-of availability, minutes, lineup, and workload context.
      </p>
      {error && (
        <StatusBanner variant="error">
          Failed to load predictions: {error.message}
        </StatusBanner>
      )}
      {loading && !data ? (
        <div className="bo-skeleton" style={{ height: 240 }} />
      ) : (data?.games.length ?? 0) === 0 ? (
        <div className="bo-empty">
          No stored predictions yet. Run{" "}
          <code>python scripts/generate_predictions.py --stage pre_tip</code>.
        </div>
      ) : (
        <ReleaseGateWarning games={data!.games} />
      )}

      {data?.games.map((g) => (
        <GameCard key={g.prediction_id} game={g} />
      ))}

      <hr className="bo-divider" />
      <p className="bo-info-text">
        Informational analysis only. The application never recommends Kelly staking while the release gate is closed.
      </p>
    </div>
  );
}

function ReleaseGateWarning({ games }: { games: PredictionGame[] }) {
  const status = games[0]?.release_gate_status ?? "shadow_only";
  if (status === "limited_paper") {
    return (
      <StatusBanner variant="warning">
        Limited paper evaluation only. The model has enough evidence for monitoring,
        but live betting remains disabled until the full production gate passes.
      </StatusBanner>
    );
  }
  if (status !== "production_ready") {
    return (
      <StatusBanner variant="error">
        Paper-only shadow mode. The production gate requires an untouched 2025 holdout,
        at least 300 priced paper bets, positive closing-line value, and clear drift checks.
      </StatusBanner>
    );
  }
  return null;
}

function GameCard({ game }: { game: PredictionGame }) {
  const [tab, setTab] = useState<typeof TABS[number]>("Rotation scenario");
  const homeProb = game.home_win_prob ?? 0.5;
  const status = game.status ?? "no_bet";
  const noBet = status !== "ready" || game.paper_only;
  return (
    <div className="bo-card">
      <div className="bo-row-between">
        <div style={{ flex: 3, minWidth: 280 }}>
          <div className="bo-info-text">{formatGameTime(game.scheduled_start)}</div>
          <h3>
            {game.away_team ?? "Away"} @ {game.home_team ?? "Home"}
          </h3>
          <ProbabilityBar
            homeProb={homeProb}
            homeLabel={game.home_team ?? "Home"}
            awayLabel={game.away_team ?? "Away"}
            height={24}
          />
        </div>
        <div style={{ flex: 2, textAlign: "right" }}>
          {noBet ? (
            <>
              <div className="bo-error" style={{ display: "inline-block" }}>
                NO BET · PAPER ONLY
              </div>
              <div className="bo-info-text" style={{ marginTop: 6 }}>
                {game.no_bet_reason ?? "Release gate has not passed."}
              </div>
            </>
          ) : (
            <ConfidenceBadge tier={game.confidence} />
          )}
          <div className="bo-info-text" style={{ marginTop: 6 }}>
            Snapshot: {game.stage ?? "unknown"} · {game.generated_at ?? ""}
          </div>
        </div>
      </div>

      <div className="bo-grid bo-grid-4" style={{ marginTop: 14 }}>
        <MetricCard label="Home win" value={pct(homeProb, 1)} />
        <MetricCard
          label="Home margin"
          value={signed(game.margin_mean, 1)}
          help={`90% interval: ${signed(game.margin_low, 1)} to ${signed(game.margin_high, 1)}`}
        />
        <MetricCard
          label="Total"
          value={num(game.total_mean, 1)}
          help={`90% interval: ${num(game.total_low, 1)} to ${num(game.total_high, 1)}`}
        />
        <MetricCard label="Scenario uncertainty" value={`${num(game.scenario_uncertainty, 1)} pts`} />
      </div>

      <div
        className="bo-grid bo-grid-4"
        style={{ marginTop: 6, color: "var(--muted-text)", fontSize: "0.85rem" }}
      >
        <span>
          De-vigged market home probability:{" "}
          {game.market_home_prob !== null && game.market_home_prob !== undefined
            ? pct(game.market_home_prob, 1)
            : "—"}
        </span>
        <span>
          Market home spread:{" "}
          {game.market_spread !== null && game.market_spread !== undefined
            ? signed(game.market_spread, 1)
            : "—"}
        </span>
        <span>
          Market total:{" "}
          {game.market_total !== null && game.market_total !== undefined
            ? num(game.market_total, 1)
            : "—"}
        </span>
        <span>
          Edge vs market:{" "}
          {game.edge !== null && game.edge !== undefined ? pct(game.edge, 1, "—") : "—"}
        </span>
      </div>

      <div className="bo-tabs" style={{ marginTop: 14 }}>
        {TABS.map((t) => (
          <div
            key={t}
            className={`bo-tab${t === tab ? " bo-tab-active" : ""}`}
            onClick={() => setTab(t)}
            role="tab"
            aria-selected={t === tab}
          >
            {t}
          </div>
        ))}
      </div>
      {tab === "Rotation scenario" && <RotationTab game={game} />}
      {tab === "Lineup matchup" && <LineupTab game={game} />}
      {tab === "Travel & context" && <TravelTab game={game} />}
      {tab === "Provenance" && <ProvenanceTab game={game} />}
    </div>
  );
}

function RotationTab({ game }: { game: PredictionGame }) {
  const initial = useMemo(
    () =>
      (game.availability ?? []).map((p) => ({
        canonical_player_id: p.canonical_player_id,
        canonical_team_id: p.canonical_team_id,
        player_name: p.player_name ?? `Player ${p.canonical_player_id ?? ""}`,
        role: p.role ?? "",
        status: p.status ?? "",
        confirmed_starter: p.confirmed_starter ?? false,
        availability_probability: p.availability_probability ?? 0.95,
        minutes_mean_if_active: p.minutes_mean_if_active ?? 0,
        minutes_sd_if_active: p.minutes_sd_if_active ?? 0,
        impact_per_minute: p.impact_per_minute ?? 0,
      })),
    [game],
  );

  const [rotation, setRotation] = useState(initial);

  if (initial.length === 0) {
    return <div className="bo-empty">No player-game history is available for a rotation scenario.</div>;
  }

  const scenarios = buildMarginScenarios(
    game.margin_mean ?? 0,
    game.margin_sd ?? 9.5,
    rotation,
    game.home_team_id ?? 0,
    game.away_team_id ?? 0,
  );
  const summary = summarizeMarginScenarios(scenarios);

  const marketSpread = game.market_spread;
  const noBet = marketSpread !== null && marketSpread !== undefined && !Number.isNaN(marketSpread)
    ? summary.scenario_uncertainty > Math.abs(-summary.margin_mean - marketSpread)
    : false;

  function update(idx: number, key: "availability_probability" | "minutes_mean_if_active", value: number) {
    setRotation((rows) => {
      const next = rows.slice();
      next[idx] = { ...next[idx], [key]: value };
      return next;
    });
  }

  return (
    <div>
      <h4>Rotation and availability scenario editor</h4>
      <p className="bo-info-text">
        Edit availability probability or active minutes to test a scenario. Edits are local to this browser session and never overwrite source observations.
      </p>
      <div className="bo-table-wrap" style={{ marginTop: 8 }}>
        <table className="bo-table">
          <thead>
            <tr>
              <th>Player</th>
              <th>Role</th>
              <th>Status</th>
              <th>Starter</th>
              <th>Play %</th>
              <th>Min if Active</th>
              <th>Min SD</th>
              <th>Impact / Min</th>
            </tr>
          </thead>
          <tbody>
            {rotation.map((row, i) => (
              <tr key={String(row.canonical_player_id ?? i)}>
                <td>{row.player_name}</td>
                <td style={{ textTransform: "capitalize" }}>{row.role}</td>
                <td style={{ textTransform: "capitalize" }}>{row.status}</td>
                <td>{row.confirmed_starter ? "✓" : ""}</td>
                <td>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={5}
                    value={Math.round((row.availability_probability ?? 0) * 100)}
                    onChange={(e) => update(i, "availability_probability", Number(e.target.value) / 100)}
                    style={{ width: 80 }}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    min={0}
                    max={50}
                    step={1}
                    value={row.minutes_mean_if_active ?? 0}
                    onChange={(e) => update(i, "minutes_mean_if_active", Number(e.target.value))}
                    style={{ width: 80 }}
                  />
                </td>
                <td>{num(row.minutes_sd_if_active, 1)}</td>
                <td>{num(row.impact_per_minute, 3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="bo-grid bo-grid-3" style={{ marginTop: 12 }}>
        <MetricCard label="Scenario home margin" value={signed(summary.margin_mean, 1)} />
        <MetricCard label="Scenario margin SD" value={num(summary.margin_sd, 1)} />
        <MetricCard
          label="Availability-only uncertainty"
          value={`${num(summary.scenario_uncertainty, 1)} pts`}
        />
      </div>
      {noBet && (
        <StatusBanner variant="warning">
          No bet: the edited availability uncertainty is larger than the apparent spread edge.
        </StatusBanner>
      )}
    </div>
  );
}

function LineupTab({ game }: { game: PredictionGame }) {
  const rows = game.lineup_matchup ?? [];
  if (rows.length === 0) {
    return <div className="bo-empty">No source lineup or inferred top-five rotation is available.</div>;
  }
  const cols: Column<typeof rows[number]>[] = [
    { key: "side", label: "Side", render: (r) => (r.side ?? "").toUpperCase() },
    { key: "rank", label: "Rank", align: "right" },
    { key: "player", label: "Player" },
    { key: "minutes_mean", label: "Min mean", align: "right", render: (r) => num(r.minutes_mean, 1) },
    { key: "minutes_sd", label: "Min SD", align: "right", render: (r) => num(r.minutes_sd, 1) },
    { key: "role", label: "Role" },
    { key: "status", label: "Status" },
    { key: "net_rating", label: "Net rating", align: "right", render: (r) => num(r.net_rating, 1) },
  ];
  return (
    <div>
      <h4>Lineup matchup and minutes uncertainty</h4>
      <DataFrame columns={cols} rows={rows} />
    </div>
  );
}

function TravelTab({ game }: { game: PredictionGame }) {
  const labels: string[] = (game.travel_context?.labels as string[]) ?? [];
  const home = (game.travel_context?.home ?? {}) as Record<string, unknown>;
  const away = (game.travel_context?.away ?? {}) as Record<string, unknown>;
  const overseas = (home?.verified_overseas_workload ?? []) as Array<Record<string, unknown>>;
  const rows = (["home", "away"] as const)
    .map((side) => {
      const r = side === "home" ? home : away;
      if (!r || Object.keys(r).length === 0) return null;
      return {
        side: side === "home" ? "Home" : "Away",
        rest_days: r.rest_days ?? null,
        games_last_4_days: r.games_last_4_days ?? null,
        games_last_7_days: r.games_last_7_days ?? null,
        travel_miles: r.travel_miles ?? null,
        timezone_shift_hours: r.timezone_shift_hours ?? null,
        is_cross_country: r.is_cross_country ?? null,
        is_early_start: r.is_early_start ?? null,
      };
    })
    .filter((x): x is NonNullable<typeof x> => x !== null);
  return (
    <div>
      <h4>Travel and workload timeline</h4>
      {labels.length > 0 && (
        <div className="bo-row" style={{ marginBottom: 8 }}>
          {labels.map((l) => (
            <span key={l} style={{ background: "var(--card-bg-alt)", padding: "2px 8px", borderRadius: 4, fontSize: "0.78rem" }}>
              {l}
            </span>
          ))}
        </div>
      )}
      {rows.length > 0 ? (
        <DataFrame
          columns={[
            { key: "side", label: "Team side" },
            { key: "rest_days", label: "Rest days", align: "right" },
            { key: "games_last_4_days", label: "Games in 4 days", align: "right" },
            { key: "games_last_7_days", label: "Games in 7 days", align: "right" },
            { key: "travel_miles", label: "Travel miles", align: "right", render: (r: any) => num(r.travel_miles, 1) },
            { key: "timezone_shift_hours", label: "TZ shift", align: "right", render: (r: any) => num(r.timezone_shift_hours, 1) },
            { key: "is_cross_country", label: "Cross-country", render: (r) => (r.is_cross_country ? "Yes" : "No") },
            { key: "is_early_start", label: "Early start", render: (r) => (r.is_early_start ? "Yes" : "No") },
          ]}
          rows={rows}
        />
      ) : (
        <div className="bo-empty">No travel/workload context available.</div>
      )}
      {Array.isArray(overseas) && overseas.length > 0 && (
        <>
          <h5 style={{ marginTop: 12 }}>Verified overseas workload</h5>
          <DataFrame columns={Object.keys(overseas[0] ?? {}).map((k) => ({ key: k, label: k }))} rows={overseas as any} />
        </>
      )}
      {(!Array.isArray(overseas) || overseas.length === 0) && (
        <div className="bo-info-text" style={{ marginTop: 8 }}>
          No verified overseas-workload observation is attached to this matchup.
        </div>
      )}
    </div>
  );
}

function ProvenanceTab({ game }: { game: PredictionGame }) {
  return (
    <pre
      style={{
        background: "var(--card-bg-alt)",
        padding: 12,
        borderRadius: 6,
        margin: 0,
        fontSize: "0.85rem",
        overflow: "auto",
      }}
    >
{JSON.stringify(
  {
    model_version: game.model_version,
    feature_schema_version: game.feature_schema_version,
    release_gate_status: game.release_gate_status,
    availability_status: game.availability_status,
    stage: game.stage,
    generated_at: game.generated_at,
  },
  null,
  2,
)}
    </pre>
  );
}

