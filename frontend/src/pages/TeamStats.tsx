import React, { useCallback, useEffect, useMemo, useState } from "react";
import { fetchTeamStats } from "../api/dataClient";
import { DataFrame, Column } from "../components/DataFrame";
import { LineChart } from "../components/LineChart";
import { MetricCard } from "../components/MetricCard";
import { StatusBanner } from "../components/StatusBanner";
import { useJson } from "../hooks/useJson";
import { TeamEntry, TeamGameSummary, TeamStatsPayload, TeamTrendPoint } from "../types/data";
import { pct } from "../utils/format";

export function TeamStats() {
  const [season, setSeason] = useState<number | null>(null);
  const defaultData = useJson<TeamStatsPayload>(useCallback(() => fetchTeamStats(), []));

  useEffect(() => {
    if (season === null && defaultData.data?.season) {
      setSeason(defaultData.data.season);
    }
  }, [season, defaultData.data]);

  const seasonData = useJson<TeamStatsPayload>(
    useCallback(() => (season === null ? Promise.resolve(defaultData.data!) : fetchTeamStats(season)), [season, defaultData.data]),
  );
  const data = season === null || season === defaultData.data?.season
    ? defaultData.data
    : seasonData.data ?? defaultData.data;
  const loading = season === null || season === defaultData.data?.season
    ? defaultData.loading
    : seasonData.loading;

  // Numeric sort matches pages/4_Team_Stats.py (sorted canonical ids), so the
  // default-selected team is the same on both apps.
  const teamIds = useMemo(
    () => Object.keys(data?.teams ?? {}).sort((a, b) => Number(a) - Number(b)),
    [data],
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => {
    if (!selectedId && teamIds.length > 0) setSelectedId(teamIds[0]!);
  }, [selectedId, teamIds]);
  const team: TeamEntry | undefined = selectedId ? data?.teams[selectedId] : undefined;

  return (
    <div>
      <h1>📊 Team Stats — {data?.season ?? season ?? "—"}</h1>
      <div style={{ display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
        <label>
          Season:{" "}
          <select
            value={season ?? data?.season ?? ""}
            onChange={(e) => setSeason(Number(e.target.value))}
            style={selectStyle}
          >
            {(data?.seasons_available ?? []).map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
        <label>
          Team:{" "}
          <select
            value={selectedId ?? ""}
            onChange={(e) => setSelectedId(e.target.value)}
            style={selectStyle}
          >
            {teamIds.map((id) => (
              <option key={id} value={id}>{data?.teams[id]?.name ?? `Team ${id}`}</option>
            ))}
          </select>
        </label>
      </div>

      {defaultData.error && (
        <StatusBanner variant="error">
          Failed to load team stats: {defaultData.error.message}
        </StatusBanner>
      )}
      {loading && !data ? (
        <div className="bo-skeleton" style={{ height: 160 }} />
      ) : !team ? (
        <div className="bo-empty">No team game stats available.</div>
      ) : (
        <TeamView team={team} />
      )}
    </div>
  );
}

function TeamView({ team }: { team: TeamEntry }) {
  const summary = team.summary;
  const trends: TeamTrendPoint[] = team.trends ?? [];
  const recentGames: TeamGameSummary[] = team.recent_games ?? [];
  return (
    <div>
      <div className="bo-grid bo-grid-4">
        <MetricCard label="Recent Win% (L10)" value={summary.win_pct_L10 !== null && summary.win_pct_L10 !== undefined ? pct(summary.win_pct_L10, 0) : "—"} />
        <MetricCard label="Pts/Game (L10)" value={summary.points_L10 !== null && summary.points_L10 !== undefined ? summary.points_L10.toFixed(1) : "—"} />
        <MetricCard label="Rest Days" value={summary.rest_days !== null && summary.rest_days !== undefined ? summary.rest_days.toFixed(0) : "—"} />
        <MetricCard
          label="Streak"
          value={summary.streak !== null && summary.streak !== undefined ? (summary.streak > 0 ? `+${summary.streak.toFixed(0)}` : summary.streak.toFixed(0)) : "—"}
        />
      </div>

      <h3 style={{ marginTop: 16 }}>Game Log</h3>
      <DataFrame<TeamGameSummary>
        columns={[
          { key: "game_date", label: "Game Date", render: (r) => gameDate(r.game_date) },
          { key: "is_home", label: "Is Home", render: (r) => (r.is_home === 1 ? "Home" : "Away") },
          { key: "points", label: "Points", align: "right", render: (r) => (r.points ?? "None") },
          { key: "win", label: "Win", render: (r) => (r.win === 1 ? "W" : "L") },
        ]}
        rows={recentGames}
        empty="No recent games."
      />

      {trends.length > 0 && (
        <>
          <h3 style={{ marginTop: 16 }}>Points Per Game (rolling)</h3>
          <LineChart
            series={[
              {
                name: "Game",
                color: "#1D428A",
                points: trends.map((t) => ({ x: t.game_date ?? "", y: t.points ?? 0 })),
              },
              {
                name: "Rolling L10",
                color: "#C8102E",
                // Skip early-season nulls (shifted L10 needs 5 prior games),
                // matching how st.line_chart drops NaN rows.
                points: trends
                  .filter((t) => t.points_L10 !== null && t.points_L10 !== undefined)
                  .map((t) => ({ x: t.game_date ?? "", y: t.points_L10! })),
              },
            ]}
          />
        </>
      )}
    </div>
  );
}

/** Format an ISO timestamp as a plain calendar date, "2026-08-05". */
function gameDate(iso: string | null): string {
  if (!iso) return "None";
  const m = /^(\d{4}-\d{2}-\d{2})/.exec(iso);
  return m ? m[1]! : iso;
}

const selectStyle: React.CSSProperties = {
  background: "var(--card-bg-alt)",
  color: "var(--text)",
  border: "1px solid var(--border-strong)",
  borderRadius: 6,
  padding: "4px 8px",
};