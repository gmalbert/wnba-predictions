import React, { useCallback, useEffect, useMemo, useState } from "react";
import { fetchStandings } from "../api/dataClient";
import { DataFrame, Column } from "../components/DataFrame";
import { StatusBanner } from "../components/StatusBanner";
import { useJson } from "../hooks/useJson";
import { StandingsPayload, StandingsRow } from "../types/data";

export function Standings() {
  const [season, setSeason] = useState<number | null>(null);
  const defaultStandings = useJson<StandingsPayload>(useCallback(() => fetchStandings(), []));

  useEffect(() => {
    if (season === null && defaultStandings.data?.season) {
      setSeason(defaultStandings.data.season);
    }
  }, [season, defaultStandings.data]);

  const seasonStandings = useJson<StandingsPayload>(
    useCallback(() => (season === null ? Promise.resolve(defaultStandings.data!) : fetchStandings(season)), [season, defaultStandings.data]),
  );

  const data = season === null || season === defaultStandings.data?.season
    ? defaultStandings.data
    : seasonStandings.data ?? defaultStandings.data;
  const loading = season === null || season === defaultStandings.data?.season
    ? defaultStandings.loading
    : seasonStandings.loading;

  const seasonsAvailable = data?.seasons_available ?? [];

  return (
    <div>
      <h1>🏆 WNBA Standings — {data?.season ?? season ?? "—"}</h1>
      <div style={{ marginBottom: 12 }}>
        <label style={{ marginRight: 8 }}>Season: </label>
        <select
          value={season ?? data?.season ?? ""}
          onChange={(e) => setSeason(Number(e.target.value))}
          style={{
            background: "var(--card-bg-alt)",
            color: "var(--text)",
            border: "1px solid var(--border-strong)",
            borderRadius: 6,
            padding: "4px 8px",
          }}
        >
          {seasonsAvailable.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
      {defaultStandings.error && (
        <StatusBanner variant="error">
          Failed to load standings: {defaultStandings.error.message}
        </StatusBanner>
      )}
      {loading && !data ? (
        <div className="bo-skeleton" style={{ height: 160 }} />
      ) : (data?.rows.length ?? 0) === 0 ? (
        <div className="bo-empty">
          No standings data available. Run <code>python scripts/daily_update.py</code> to fetch.
        </div>
      ) : (
        <ConferenceGroups rows={data!.rows} />
      )}
    </div>
  );
}

function ConferenceGroups({ rows }: { rows: StandingsRow[] }) {
  const groups = useMemo(() => {
    const withConf = rows.filter((r) => r.conference);
    if (withConf.length === 0) {
      return [{ label: null as string | null, rows }];
    }
    const conferences = Array.from(new Set(withConf.map((r) => r.conference ?? "")));
    return conferences.map((c) => ({
      label: c,
      rows: withConf.filter((r) => r.conference === c),
    }));
  }, [rows]);
  return (
    <div>
      {groups.map((g) => (
        <div key={g.label ?? "_"} style={{ marginBottom: 18 }}>
          {g.label && <h3>{g.label}</h3>}
          <DataFrame
            columns={[
              // Mirrors pages/3_Standings.py COLUMN_SPECS (labels + nickname).
              { key: "team", label: "Team", render: (r) => r.nickname ?? r.team },
              { key: "wins", label: "Wins", align: "right" },
              { key: "losses", label: "Losses", align: "right" },
              { key: "win_pct", label: "Win %", align: "right", render: (r) => r.win_pct !== null && r.win_pct !== undefined ? r.win_pct.toFixed(3) : "—" },
              { key: "streak", label: "Streak" },
              { key: "playoff_rank", label: "Playoff Rank", align: "right" },
              { key: "conference", label: "Conference" },
              { key: "home_record", label: "Home Record" },
              { key: "road_record", label: "Road Record" },
              { key: "l10", label: "Last 10" },
              { key: "points_per_game", label: "Points/Game", align: "right", render: (r) => r.points_per_game !== null && r.points_per_game !== undefined ? r.points_per_game.toFixed(1) : "—" },
              { key: "opp_points_per_game", label: "Opp Points/Game", align: "right", render: (r) => r.opp_points_per_game !== null && r.opp_points_per_game !== undefined ? r.opp_points_per_game.toFixed(1) : "—" },
              { key: "point_diff", label: "Point Diff", align: "right", render: (r) => r.point_diff !== null && r.point_diff !== undefined ? r.point_diff.toFixed(1) : "—" },
            ]}
            rows={g.rows
              .slice()
              .sort((a, b) => (b.wins ?? -1) - (a.wins ?? -1))}
          />
        </div>
      ))}
    </div>
  );
}