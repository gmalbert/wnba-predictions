import React, { useCallback, useMemo, useState } from "react";
import { fetchModelPerformance } from "../api/dataClient";
import { DataFrame, Column } from "../components/DataFrame";
import { MetricCard } from "../components/MetricCard";
import { StatusBanner } from "../components/StatusBanner";
import { useJson } from "../hooks/useJson";
import { ModelPerformancePayload } from "../types/data";
import { num, pct } from "../utils/format";

const SEGMENT_TABS = ["travel", "rest", "roster_continuity", "season_phase", "data_source"] as const;

export function ModelPerformance() {
  const { data, loading, error } = useJson<ModelPerformancePayload>(
    useCallback(() => fetchModelPerformance(), []),
  );

  return (
    <div>
      <h1>📈 Model Performance</h1>
      {error && (
        <StatusBanner variant="error">
          Failed to load model performance: {error.message}
        </StatusBanner>
      )}
      {loading && !data ? (
        <div className="bo-skeleton" style={{ height: 240 }} />
      ) : !data ? (
        <div className="bo-empty">No evaluation metrics available.</div>
      ) : (
        <Body data={data} />
      )}
    </div>
  );
}

/** Canonical check order, matching the pipeline's eval_metrics.json (the
 * exported release_gate.json is key-sorted, so we restore the source order). */
const CHECK_ORDER = [
  "untouched_2025_holdout",
  "minimum_300_priced_bets",
  "positive_clv",
  "drift_clear",
];

function Body({ data }: { data: ModelPerformancePayload }) {
  const gate = data.release_gate;
  const rawChecks = gate.checks ?? {};
  const checks = Object.entries(rawChecks).sort(
    ([a], [b]) => {
      const ia = CHECK_ORDER.indexOf(a);
      const ib = CHECK_ORDER.indexOf(b);
      return (ia === -1 ? CHECK_ORDER.length : ia) - (ib === -1 ? CHECK_ORDER.length : ib);
    },
  );
  const metrics = data.win_model ?? {};
  const calibration = data.winner_calibration ?? { ece: null, null: null, bins: [] };
  const margin = data.margin ?? {};
  const totals = data.totals ?? {};
  const baselines = data.baselines ?? {};
  const ledger = data.paper_ledger ?? {
    priced_bets: 0,
    graded_bets: 0,
    mean_clv: null,
    roi: null,
    profit_units: 0,
    by_market: [],
  };
  const segments = data.segment_performance ?? {};

  return (
    <div>
      <h3>Production release gate</h3>
      {gate.status === "production_ready" ? (
        <StatusBanner variant="success">Production release gate passed.</StatusBanner>
      ) : (
        <StatusBanner variant="error">Shadow/paper-only artifact. Live betting use is suspended.</StatusBanner>
      )}
      <div className="bo-grid" style={{ gridTemplateColumns: `repeat(${Math.max(checks.length, 1)}, 1fr)`, gap: 8 }}>
        {checks.map(([name, ok]) => (
          <div
            className="bo-metric"
            style={{
              background: ok ? "rgba(22,163,74,0.16)" : "rgba(153,27,27,0.18)",
              borderRadius: 6,
              padding: "8px 10px",
              textAlign: "center",
            }}
            key={name}
          >
            <div style={{ fontSize: "0.78rem", color: "var(--muted-text)" }}>
              {name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
            </div>
            <div style={{ fontSize: "1.05rem", fontWeight: 700, marginTop: 4 }}>
              {ok ? "PASS" : "FAIL"}
            </div>
          </div>
        ))}
      </div>
      <p className="bo-info-text" style={{ marginTop: 6 }}>
        Rows: {data.n_rows.toLocaleString()} · Seasons: [{(data.seasons ?? []).join(", ")}] · Untouched holdout: {data.holdout_season ?? "—"} ({data.holdout_rows.toLocaleString()} games)
      </p>

      <h3 style={{ marginTop: 18 }}>Untouched {data.holdout_season ?? 2025} winner score</h3>
      <div className="bo-grid bo-grid-4">
        <MetricCard label="Accuracy" value={pct(metrics.accuracy ?? null, 1)} />
        <MetricCard label="Log loss" value={num(metrics.log_loss ?? null, 3)} />
        <MetricCard label="Brier score" value={num(metrics.brier_score ?? null, 3)} />
        <MetricCard label="Games" value={metrics.n_test ?? data.holdout_rows} />
      </div>
      {calibration.ece !== null && calibration.ece !== undefined && (
        <p className="bo-info-text" style={{ marginTop: 6 }}>
          Winner calibration: ECE {calibration.ece?.toFixed(3)} · maximum calibration error {calibration.mce?.toFixed(3)}
        </p>
      )}
      {calibration.bins && calibration.bins.length > 0 && (
        <details>
          <summary>Winner reliability bins</summary>
          <DataFrame
            columns={[
              { key: "lower", label: "Lower", align: "right", render: (r) => num(r.lower, 3) },
              { key: "upper", label: "Upper", align: "right", render: (r) => num(r.upper, 3) },
              { key: "n", label: "N", align: "right" },
              { key: "mean_probability", label: "Mean prob", align: "right", render: (r) => num(r.mean_probability, 4) },
              { key: "observed_rate", label: "Observed rate", align: "right", render: (r) => num(r.observed_rate, 4) },
              { key: "absolute_error", label: "Abs error", align: "right", render: (r) => num(r.absolute_error, 4) },
            ]}
            rows={calibration.bins}
          />
        </details>
      )}

      <h3 style={{ marginTop: 18 }}>Calibrated continuous distributions</h3>
      <DataFrame
        columns={[
          // Raw headers + unrounded values mirror the Streamlit st.dataframe.
          { key: "target", label: "target" },
          { key: "mae", label: "MAE", align: "right", render: (r: any) => rawNum(r.mae) },
          { key: "rmse", label: "RMSE", align: "right", render: (r: any) => rawNum(r.rmse) },
          { key: "crps", label: "CRPS", align: "right", render: (r: any) => rawNum(r.crps) },
          { key: "interval_90_coverage", label: "90% coverage", align: "right", render: (r: any) => rawNum(r.interval_90_coverage) },
          { key: "residual_sd", label: "residual SD", align: "right", render: (r: any) => rawNum(r.residual_sd) },
        ]}
        rows={[
          { target: "Margin", ...margin },
          { target: "Total", ...totals },
        ].filter((r) => Object.keys(r).length > 1) as any}
        empty="No recent distribution score is available yet."
      />

      {data.walk_forward && data.walk_forward.length > 0 && (
        <>
          <h3 style={{ marginTop: 18 }}>Expanding-season folds with recency weighting</h3>
          <DataFrame
            columns={[
              { key: "train_through", label: "Train through", align: "right" },
              { key: "test_season", label: "Test season", align: "right" },
              { key: "n_train", label: "N train", align: "right" },
              { key: "n_test", label: "N test", align: "right" },
              { key: "accuracy", label: "Accuracy", align: "right", render: (r) => num(r.accuracy, 4) },
              { key: "log_loss", label: "Log loss", align: "right", render: (r) => num(r.log_loss, 3) },
              { key: "brier_score", label: "Brier", align: "right", render: (r) => num(r.brier_score, 3) },
            ]}
            rows={data.walk_forward}
          />
        </>
      )}

      <h3 style={{ marginTop: 18 }}>Baselines and market-relative scoring</h3>
      <BaselineRows baselines={baselines} />

      {(data.line_bucket_calibration?.spread?.length || data.line_bucket_calibration?.total?.length) ? (
        <>
          <h3 style={{ marginTop: 18 }}>Line-bucket calibration</h3>
          <div className="bo-grid bo-grid-2">
            <div>
              <h4>Spread</h4>
              <DataFrame
                columns={[
                  { key: "lower", label: "Lower", align: "right", render: (r: any) => num(r.lower, 3) },
                  { key: "upper", label: "Upper", align: "right", render: (r: any) => num(r.upper, 3) },
                  { key: "n", label: "N", align: "right", render: (r: any) => num(r.n, 0) },
                  { key: "observed_rate", label: "Observed rate", align: "right", render: (r: any) => num(r.observed_rate, 4) },
                ]}
                rows={(data.line_bucket_calibration?.spread ?? []) as any}
                empty="No spread buckets."
              />
            </div>
            <div>
              <h4>Total</h4>
              <DataFrame
                columns={[
                  { key: "lower", label: "Lower", align: "right", render: (r: any) => num(r.lower, 3) },
                  { key: "upper", label: "Upper", align: "right", render: (r: any) => num(r.upper, 3) },
                  { key: "n", label: "N", align: "right", render: (r: any) => num(r.n, 0) },
                  { key: "observed_rate", label: "Observed rate", align: "right", render: (r: any) => num(r.observed_rate, 4) },
                ]}
                rows={(data.line_bucket_calibration?.total ?? []) as any}
                empty="No total buckets."
              />
            </div>
          </div>
        </>
      ) : null}

      <h3 style={{ marginTop: 18 }}>2026 frozen paper ledger</h3>
      <div className="bo-grid bo-grid-4">
        <MetricCard label="Priced bets" value={ledger.priced_bets ?? 0} help="Release gate requires at least 300." />
        <MetricCard label="Graded bets" value={ledger.graded_bets ?? 0} />
        <MetricCard
          label="Mean CLV"
          value={ledger.mean_clv !== null && ledger.mean_clv !== undefined ? (ledger.mean_clv >= 0 ? `+${ledger.mean_clv.toFixed(3)}` : ledger.mean_clv.toFixed(3)) : "—"}
        />
        <MetricCard
          label="Flat-stake ROI"
          value={ledger.roi !== null && ledger.roi !== undefined ? pct(ledger.roi, 1) : "—"}
        />
      </div>
      {ledger.by_market && ledger.by_market.length > 0 && (
        <DataFrame
          columns={[
            { key: "market", label: "Market" },
            { key: "bets", label: "Bets", align: "right" },
            { key: "profit_units", label: "Profit units", align: "right", render: (r: any) => num(r.profit_units, 3) },
            { key: "roi", label: "ROI", align: "right", render: (r: any) => num(r.roi, 4) },
          ]}
          rows={ledger.by_market}
        />
      )}

      <h3 style={{ marginTop: 18 }}>Drift and automatic suspension</h3>
      {data.drift?.suspended ? (
        <StatusBanner variant="error">
          Suspended: maximum PSI is {num(data.drift.max_psi, 3)} (threshold 0.25).
        </StatusBanner>
      ) : (
        <StatusBanner variant="success">
          Drift clear: maximum PSI is {num(data.drift?.max_psi ?? 0, 3)}.
        </StatusBanner>
      )}
      {data.drift?.warning_features && data.drift.warning_features.length > 0 && (
        <p className="bo-info-text">Shifted features: {data.drift.warning_features.join(", ")}</p>
      )}

      <h3 style={{ marginTop: 18 }}>Performance by WNBA context</h3>
      <Segments segments={segments} />

      <p className="bo-info-text" style={{ marginTop: 18 }}>
        Artifacts: <code>data_files/wnba/model_artifacts/</code>
      </p>
    </div>
  );
}

/** Raw value the way st.dataframe prints it (null → "None"). */
function rawNum(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "None";
  return String(value);
}

function BaselineRows({ baselines }: { baselines: Record<string, any> }) {
  const rows: Array<Record<string, unknown>> = [];
  for (const name of ["elo", "simple_efficiency"]) {
    const v = baselines[name];
    if (v && Object.keys(v).length > 0) {
      rows.push({ baseline: name.replace("_", " ").replace(/\b\w/, (c) => c.toUpperCase()), ...v });
    }
  }
  const market = (baselines.market ?? {}) as Record<string, any>;
  if (market.winner) {
    const w = market.winner;
    if (w.model) rows.push({ baseline: "Model on priced games", ...w.model, n: w.n_priced });
    if (w.market) rows.push({ baseline: "De-vigged close", ...w.market, n: w.n_priced });
  }
  if (rows.length === 0) {
    return (
      <div className="bo-empty">No aligned recent-season market snapshots are available for comparison.</div>
    );
  }
  return (
    <DataFrame
      columns={[
        { key: "baseline", label: "Baseline" },
        { key: "accuracy", label: "Accuracy", align: "right", render: (r: any) => num(r.accuracy, 4) },
        { key: "log_loss", label: "Log loss", align: "right", render: (r: any) => num(r.log_loss, 4) },
        { key: "brier_score", label: "Brier", align: "right", render: (r: any) => num(r.brier_score, 4) },
        { key: "n", label: "N", align: "right", render: (r: any) => num(r.n, 0) },
      ]}
      rows={rows as any}
    />
  );
}

function Segments({ segments }: { segments: Record<string, Array<Record<string, unknown>>> }) {
  const present = SEGMENT_TABS.filter((s) => segments[s] && segments[s]!.length > 0);
  const [active, setActive] = useState<typeof present[number] | null>(null);
  const tab = active ?? present[0] ?? null;
  return (
    <div>
      <div className="bo-tabs">
        {present.map((s) => (
          <div
            key={s}
            className={`bo-tab${s === tab ? " bo-tab-active" : ""}`}
            onClick={() => setActive(s)}
          >
            {s.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </div>
        ))}
      </div>
      {tab ? (
        <DataFrame
          columns={[
            { key: "segment", label: "Segment" },
            { key: "n", label: "N", align: "right", render: (r: any) => num(r.n, 0) },
            { key: "accuracy", label: "Accuracy", align: "right", render: (r: any) => num(r.accuracy, 4) },
            { key: "log_loss", label: "Log loss", align: "right", render: (r: any) => num(r.log_loss, 4) },
            { key: "brier_score", label: "Brier", align: "right", render: (r: any) => num(r.brier_score, 4) },
            { key: "margin_mae", label: "Margin MAE", align: "right", render: (r: any) => num(r.margin_mae, 3) },
            { key: "total_mae", label: "Total MAE", align: "right", render: (r: any) => num(r.total_mae, 3) },
          ]}
          rows={segments[tab] ?? []}
          empty={`No ${tab.replace("_", " ")} segments.`}
        />
      ) : (
        <div className="bo-empty">No segment performance data available.</div>
      )}
    </div>
  );
}