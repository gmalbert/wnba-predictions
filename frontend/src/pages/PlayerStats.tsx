import React, { useCallback, useEffect, useMemo, useState } from "react";
import { fetchPlayerStats } from "../api/dataClient";
import { DataFrame, Column } from "../components/DataFrame";
import { LineChart } from "../components/LineChart";
import { MetricCard } from "../components/MetricCard";
import { StatusBanner } from "../components/StatusBanner";
import { useJson } from "../hooks/useJson";
import { PlayerEntry, PlayerGameSummary, PlayerStatsPayload, PlayerTrendPoint } from "../types/data";

export function PlayerStats() {
  const [season, setSeason] = useState<number | null>(null);
  const defaultData = useJson<PlayerStatsPayload>(useCallback(() => fetchPlayerStats(), []));

  useEffect(() => {
    if (season === null && defaultData.data?.season) {
      setSeason(defaultData.data.season);
    }
  }, [season, defaultData.data]);

  const seasonData = useJson<PlayerStatsPayload>(
    useCallback(() => (season === null ? Promise.resolve(defaultData.data!) : fetchPlayerStats(season)), [season, defaultData.data]),
  );
  const data = season === null || season === defaultData.data?.season
    ? defaultData.data
    : seasonData.data ?? defaultData.data;
  const loading = season === null || season === defaultData.data?.season
    ? defaultData.loading
    : seasonData.loading;

  // Numeric sort matches pages/5_Player_Stats.py (sorted canonical ids), so the
  // default-selected player is the same on both apps.
  const playerIds = useMemo(
    () => Object.keys(data?.players ?? {}).sort((a, b) => Number(a) - Number(b)),
    [data],
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => {
    if (!selectedId && playerIds.length > 0) setSelectedId(playerIds[0]!);
  }, [selectedId, playerIds]);

  const player: PlayerEntry | undefined = selectedId ? data?.players[selectedId] : undefined;

  return (
    <div>
      <h1>👤 Player Stats — {data?.season ?? season ?? "—"}</h1>
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
          Player:{" "}
          <select
            value={selectedId ?? ""}
            onChange={(e) => setSelectedId(e.target.value)}
            style={selectStyle}
          >
            {playerIds.map((id) => (
              <option key={id} value={id}>{data?.players[id]?.name ?? `Player ${id}`}</option>
            ))}
          </select>
        </label>
      </div>

      {defaultData.error && (
        <StatusBanner variant="error">
          Failed to load player stats: {defaultData.error.message}
        </StatusBanner>
      )}
      {loading && !data ? (
        <div className="bo-skeleton" style={{ height: 160 }} />
      ) : !player ? (
        <div className="bo-empty">No player game stats available.</div>
      ) : (
        <PlayerView player={player} />
      )}
    </div>
  );
}

function PlayerView({ player }: { player: PlayerEntry }) {
  const summary = player.summary;
  const trends: PlayerTrendPoint[] = player.trends ?? [];
  const recentGames: PlayerGameSummary[] = player.recent_games ?? [];

  return (
    <div>
      <div className="bo-grid bo-grid-4">
        <MetricCard label="Games" value={summary.games ?? "—"} />
        <MetricCard label="Pts/Game" value={summary.ppg !== null && summary.ppg !== undefined ? summary.ppg.toFixed(1) : "—"} />
        <MetricCard label="Pts/40 (L10)" value={summary.ppg_per40_L10 !== null && summary.ppg_per40_L10 !== undefined ? summary.ppg_per40_L10.toFixed(1) : "—"} />
        <MetricCard label="Ast/40 (L10)" value={summary.apg_per40_L10 !== null && summary.apg_per40_L10 !== undefined ? summary.apg_per40_L10.toFixed(1) : "—"} />
      </div>

      <h3 style={{ marginTop: 16 }}>Recent Game Log</h3>
      <DataFrame<PlayerGameSummary>
        columns={[
          { key: "game_date", label: "Game Date", render: (r) => gameDate(r.game_date) },
          { key: "points", label: "Points", align: "right", render: (r) => raw(r.points) },
          { key: "rebounds", label: "Rebounds", align: "right", render: (r) => raw(r.rebounds) },
          { key: "assists", label: "Assists", align: "right", render: (r) => raw(r.assists) },
          { key: "minutes", label: "Minutes", align: "right", render: (r) => raw(r.minutes) },
          { key: "points_per40", label: "Points Per 40", align: "right", render: (r) => raw(r.points_per40) },
        ]}
        rows={recentGames}
        empty="No recent games."
      />

      {trends.length >= 3 && (
        <>
          <h3 style={{ marginTop: 16 }}>Points Per Game</h3>
          <LineChart
            series={[
              {
                name: "Points",
                color: "#F03060",
                points: trends.map((t) => ({ x: t.game_date ?? "", y: t.points ?? 0 })),
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

/** Raw value the way st.dataframe prints it: up to 4 decimals, trailing
 * zeros stripped (null → "None"). */
function raw(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "None";
  return String(Math.round(value * 1e4) / 1e4);
}

const selectStyle: React.CSSProperties = {
  background: "var(--card-bg-alt)",
  color: "var(--text)",
  border: "1px solid var(--border-strong)",
  borderRadius: 6,
  padding: "4px 8px",
};