import React from "react";

interface Props {
  label: string;
  value: React.ReactNode;
  help?: string;
}

/** Mirrors Streamlit's `st.metric` — large value, small label, optional tooltip. */
export function MetricCard({ label, value, help }: Props) {
  return (
    <div
      className="bo-metric"
      title={help}
      style={{
        background: "var(--card-bg, #1d1429)",
        borderRadius: "0.5rem",
        padding: "12px 14px",
        border: "1px solid var(--card-border, rgba(255,255,255,0.08))",
        minHeight: "72px",
      }}
    >
      <div
        style={{
          fontSize: "0.78rem",
          color: "var(--muted-text, #9aa0b4)",
          textTransform: "none",
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: "1.45rem", fontWeight: 700, marginTop: "4px" }}>{value}</div>
    </div>
  );
}