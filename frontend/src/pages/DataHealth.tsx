import React, { useCallback, useMemo } from "react";
import { fetchDataHealth, fetchModelPerformance } from "../api/dataClient";
import { DataFrame, Column } from "../components/DataFrame";
import { MetricCard } from "../components/MetricCard";
import { StatusBanner } from "../components/StatusBanner";
import { useJson } from "../hooks/useJson";
import { DataHealthPayload, DataHealthSource, ModelPerformancePayload } from "../types/data";
import { ageHours, classifyStatus } from "../utils/format";

export function DataHealth() {
  const dataHealth = useJson<DataHealthPayload>(useCallback(() => fetchDataHealth(), []));
  const metrics = useJson<ModelPerformancePayload>(useCallback(() => fetchModelPerformance(), []));

  return (
    <div>
      <h1>🩺 Data Health</h1>
      <p className="bo-page-caption">
        Source metadata drives this panel; missing and stale observations are never silently substituted.
      </p>
      {dataHealth.error && (
        <StatusBanner variant="error">
          Failed to load data health: {dataHealth.error.message}
        </StatusBanner>
      )}

      {dataHealth.loading && !dataHealth.data ? (
        <div className="bo-skeleton" style={{ height: 240 }} />
      ) : (
        <Body dataHealth={dataHealth.data} metrics={metrics.data} />
      )}
    </div>
  );
}

function Body({
  dataHealth,
  metrics,
}: {
  dataHealth: DataHealthPayload | null;
  metrics: ModelPerformancePayload | null;
}) {
  const sources = (dataHealth?.sources ?? []).map((s) => ({
    ...s,
    age_hours: ageHours(s.last_success),
    status: classifyStatus(s.ok),
  }));
  const failed = sources.filter((s) => s.ok === false);
  const capability = dataHealth?.capability_registry ?? [];
  const safety = dataHealth?.artifact_safety ?? null;
  const coverage = dataHealth?.as_of_coverage ?? [];

  return (
    <div>
      <h3>Adapter source status</h3>
      <DataFrame<DataHealthSource & { age_hours: number | null; status: string }>
        columns={[
          // Raw headers + values mirror the Streamlit st.dataframe output.
          { key: "source", label: "source" },
          { key: "data_type", label: "data_type" },
          { key: "status", label: "status" },
          { key: "last_success", label: "last_success", render: (r) => (r.last_success ?? "None") },
          { key: "last_attempt", label: "last_attempt", render: (r) => (r.last_attempt ?? "None") },
          { key: "age_hours", label: "age_hours", align: "right", render: (r) => (r.age_hours === null ? "None" : r.age_hours.toFixed(1)) },
          { key: "records", label: "records", align: "right", render: (r) => (r.records ?? 0).toLocaleString() },
          { key: "error", label: "error", render: (r) => (r.error ?? "None") },
        ]}
        rows={sources as any}
        empty="No source-health records yet."
      />
      {failed.length > 0 && (
        <StatusBanner variant="warning">
          {failed.length} source/data combinations failed their latest attempt.
        </StatusBanner>
      )}

      <h3 style={{ marginTop: 18 }}>Capability and fallback registry</h3>
      <DataFrame
        columns={[
          { key: "data_type", label: "data type" },
          { key: "priority", label: "priority", align: "right" },
          { key: "source", label: "source" },
        ]}
        rows={capability}
      />

      <h3 style={{ marginTop: 18 }}>Artifact safety</h3>
      <div className="bo-grid bo-grid-4">
        <MetricCard label="League" value={safety?.league ?? "—"} />
        <MetricCard label="Season" value={safety?.season ?? "—"} />
        <MetricCard label="Schema" value={safety?.schema ?? "—"} />
        <MetricCard label="Artifact" value={safety?.artifact ?? "—"} />
      </div>
      {metrics?.release_gate?.status !== "production_ready" && (
        <StatusBanner variant="error">
          Stale/unvalidated artifacts are automatically presented as no-bet, paper-only projections.
        </StatusBanner>
      )}
      {metrics && (
        <p className="bo-info-text" style={{ marginTop: 6 }}>
          Training coverage: [{(metrics.seasons ?? []).join(", ")}] · {metrics.n_rows.toLocaleString()} rows · Holdout: {metrics.holdout_season ?? "—"} · <code>data_files/wnba/model_artifacts/</code>
        </p>
      )}

      <h3 style={{ marginTop: 18 }}>As-of coverage expectations</h3>
      <DataFrame
        columns={[
          { key: "dataset", label: "dataset" },
          { key: "required_history", label: "required history" },
          { key: "policy", label: "policy" },
        ]}
        rows={coverage}
      />
    </div>
  );
}