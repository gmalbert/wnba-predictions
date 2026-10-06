import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchManifest,
  fetchModelPerformance,
  fetchPredictions,
  fetchReleaseGate,
} from "../api/dataClient";
import { ConfidenceBadge, NoBetBadge } from "../components/ConfidenceBadge";
import { MetricCard } from "../components/MetricCard";
import { ProbabilityBar } from "../components/ProbabilityBar";
import { StatusBanner } from "../components/StatusBanner";
import { useJson } from "../hooks/useJson";
import {
  Manifest,
  ModelPerformancePayload,
  PredictionsPayload,
  ReleaseGatePayload,
} from "../types/data";
import { formatToday, formatTimestamp, pct, signed } from "../utils/format";

export function Home() {
  const manifest = useJson<Manifest>(useCallback(() => fetchManifest(), []));
  const predictions = useJson<PredictionsPayload>(useCallback(() => fetchPredictions(), []));
  const releaseGate = useJson<ReleaseGatePayload>(useCallback(() => fetchReleaseGate(), []));
  const model = useJson<ModelPerformancePayload>(useCallback(() => fetchModelPerformance(), []));

  const loading =
    manifest.loading || predictions.loading || releaseGate.loading || model.loading;
  const error =
    manifest.error || predictions.error || releaseGate.error || model.error;

  return (
    <div>
      <div className="bo-page-title">
        <img src="./logo.png" alt="WNBA Predictions" width={130} />
        <div>
          <h1>WNBA Predictions</h1>
          <p style={{ color: "var(--muted-text-2)", marginTop: 2 }}>
            Season {manifest.data?.season ?? "—"} · {formatToday()}
          </p>
        </div>
      </div>
      <hr className="bo-divider" />

      {error && (
        <StatusBanner variant="error">
          Failed to load home data: {error.message}
        </StatusBanner>
      )}

      {/* Release-gate warning — mirrors predictions.py:home_page */}
      {releaseGate.data && releaseGate.data.status !== "production_ready" && (
        <StatusBanner variant="error">
          Paper-only shadow mode: the recent-season holdout, 300 priced bets,
          positive CLV, and drift release gate has not passed.
        </StatusBanner>
      )}

      <HeroMetrics predictions={predictions.data} model={model.data} loading={loading} />

      <hr className="bo-divider" />

      <MatchupList loading={loading} data={predictions.data} />

      <hr className="bo-divider" />

      <ExploreTiles />

      {manifest.data && (
        <p className="bo-info-text" style={{ marginTop: 12 }}>
          Data generated at {formatTimestamp(manifest.data.generated_at)} · model{" "}
          <code>{manifest.data.model_version}</code> · feature schema{" "}
          <code>{manifest.data.feature_schema_version}</code>
        </p>
      )}
    </div>
  );
}

function HeroMetrics({
  predictions,
  model,
  loading,
}: {
  predictions: PredictionsPayload | null;
  model: ModelPerformancePayload | null;
  loading: boolean;
}) {
  const games = predictions?.games ?? [];
  const totalGames = games.length;
  const ready = games.filter((g) => g.status === "ready");
  const high = ready.filter((g) => g.confidence === "High").length;
  const med = ready.filter((g) => g.confidence === "Medium").length;
  const avgConv = useMemo(() => {
    // Mirrors predictions.py:home_page — mean over ALL games, not just ready ones.
    if (games.length === 0) return null;
    const vals = games.map((g) => {
      const hp = Math.min(Math.max(g.home_win_prob ?? 0.5, 0), 0.99);
      return Math.max(hp, 1 - hp);
    });
    const sum = vals.reduce((a, b) => a + b, 0);
    return sum / vals.length;
  }, [games]);
  const accuracy = model?.win_model?.accuracy ?? null;

  if (loading && totalGames === 0) {
    return (
      <div className="bo-grid bo-grid-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="bo-skeleton" style={{ height: 72 }} />
        ))}
      </div>
    );
  }
  return (
    <div className="bo-grid bo-grid-5">
      <MetricCard label="Upcoming Games" value={totalGames} />
      <MetricCard label="High Confidence" value={high} />
      <MetricCard label="Medium Confidence" value={med} />
      <MetricCard
        label="Avg Conviction"
        value={avgConv !== null ? pct(avgConv, 0) : "—"}
      />
      <MetricCard
        label="2025 Holdout Accuracy"
        value={accuracy !== null ? pct(accuracy, 1) : "—"}
        help="Ensemble accuracy on held-out games."
      />
    </div>
  );
}

function MatchupList({
  loading,
  data,
}: {
  loading: boolean;
  data: PredictionsPayload | null;
}) {
  if (loading && !data) {
    return <div className="bo-skeleton" style={{ height: 160 }} />;
  }
  const games = data?.games ?? [];
  if (games.length === 0) {
    return (
      <div className="bo-empty">
        No upcoming games found, or data hasn't been generated yet. Run{" "}
        <code>scripts/daily_update.py</code> to populate.
      </div>
    );
  }
  return (
    <div>
      <h3 style={{ marginBottom: 12 }}>🏀 Upcoming Matchups ({games.length})</h3>
      <div className="bo-card-stack">
        {games.map((g) => {
          const home = g.home_team ?? "Home";
          const away = g.away_team ?? "Away";
          const hp = g.home_win_prob ?? 0.5;
          const conf = g.confidence ?? "Low";
          const noBet = g.status !== "ready" || g.paper_only;
          const spread = g.predicted_spread;
          let spreadStr = "";
          if (spread !== null && spread !== undefined && !Number.isNaN(spread)) {
            const fav = spread < 0 ? home : away;
            spreadStr = ` · ${fav} -${Math.abs(spread).toFixed(1)}`;
          }
          return (
            <div key={g.prediction_id} className="bo-card">
              <div className="bo-row-between">
                <div style={{ flex: 5, minWidth: 280 }}>
                  <strong style={{ fontSize: "1.05rem" }}>
                    {away} @ {home}
                    {spreadStr}
                  </strong>
                  <div style={{ marginTop: 6 }}>
                    <ProbabilityBar homeProb={hp} homeLabel={home} awayLabel={away} />
                  </div>
                </div>
                <div style={{ flex: 2, textAlign: "right" }}>
                  {noBet ? (
                    <>
                      <NoBetBadge />
                      <div className="bo-info-text" style={{ marginTop: 6 }}>
                        {g.no_bet_reason ?? "Release gate has not passed."}
                      </div>
                    </>
                  ) : (
                    <>
                      <ConfidenceBadge tier={conf} />
                      <div className="bo-info-text" style={{ marginTop: 6 }}>
                        Pick: {hp >= 0.5 ? home : away}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ExploreTiles() {
  const tiles = [
    { icon: "🏀", title: "Game Predictions", desc: "Matchups, edges & confidence", to: "/game-predictions" },
    { icon: "🏆", title: "Standings", desc: "League standings", to: "/standings" },
    { icon: "📊", title: "Team Stats", desc: "Team metrics & trends", to: "/team-stats" },
    { icon: "👤", title: "Player Stats", desc: "Player dashboards", to: "/player-stats" },
    { icon: "📈", title: "Model Performance", desc: "Accuracy & calibration", to: "/model-performance" },
  ];
  return (
    <div>
      <h3>Explore</h3>
      <div className="bo-grid bo-grid-5">
        {tiles.map((t) => (
          <Link key={t.to} to={t.to} className="bo-tile">
            <div className="bo-tile-icon">{t.icon}</div>
            <div className="bo-tile-label">{t.title}</div>
            <div className="bo-tile-caption">{t.desc}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}