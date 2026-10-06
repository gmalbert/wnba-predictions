import React from "react";

export interface Column<T> {
  key: string;
  label: string;
  render?: (row: T) => React.ReactNode;
  align?: "left" | "right" | "center";
  width?: string;
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  empty?: React.ReactNode;
}

export function DataFrame<T>({ columns, rows, empty }: Props<T>) {
  if (!rows || rows.length === 0) {
    return (
      <div style={{ padding: "12px", color: "var(--muted-text, #94a3b8)" }}>
        {empty ?? "No rows."}
      </div>
    );
  }
  return (
    <div style={{ overflowX: "auto", borderRadius: "0.5rem", border: "1px solid rgba(255,255,255,0.08)" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.92rem" }}>
        <thead>
          <tr style={{ background: "var(--card-bg, #1d1429)" }}>
            {columns.map((col) => (
              <th
                key={col.key}
                style={{
                  padding: "8px 10px",
                  textAlign: col.align ?? "left",
                  width: col.width,
                  fontWeight: 600,
                  color: "var(--muted-text, #cbd5e1)",
                }}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              style={{
                borderTop: "1px solid rgba(255,255,255,0.04)",
                background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.02)",
              }}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  style={{
                    padding: "7px 10px",
                    textAlign: col.align ?? "left",
                    whiteSpace: "nowrap",
                  }}
                >
                  {col.render ? col.render(row) : (row as Record<string, unknown>)[col.key] as React.ReactNode}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}