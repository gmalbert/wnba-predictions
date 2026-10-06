import React from "react";

export interface SeriesPoint {
  x: string;
  y: number;
}

interface Props {
  series: Array<{ name: string; color: string; points: SeriesPoint[] }>;
  height?: number;
  width?: number;
  yLabel?: string;
  xLabel?: string;
}

/** Lightweight inline SVG line chart used by Team Stats / Player Stats.
 *  We deliberately avoid pulling in a chart library: parity with Streamlit's
 *  simple `st.line_chart` is the goal, and the data shape is small.
 */
export function LineChart({ series, height = 220, width = 720, yLabel, xLabel }: Props) {
  const padding = { left: 48, right: 12, top: 12, bottom: 28 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  const allPoints = series.flatMap((s) => s.points);
  if (allPoints.length === 0) {
    return (
      <div style={{ padding: "12px", color: "var(--muted-text, #94a3b8)" }}>
        No data to plot.
      </div>
    );
  }
  const xs = allPoints.map((p) => p.x);
  const ys = allPoints.map((p) => p.y);
  const xMin = xs[0]!;
  const xMax = xs[xs.length - 1]!;
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const yRange = yMax - yMin || 1;

  function xScale(v: string) {
    const all = xs;
    if (all.length <= 1) return padding.left;
    const idx = all.indexOf(v);
    if (idx < 0) return padding.left;
    return padding.left + (idx / (all.length - 1)) * innerW;
  }
  function yScale(v: number) {
    return padding.top + innerH - ((v - yMin) / yRange) * innerH;
  }

  // Choose ~5 x-axis ticks evenly spaced
  const ticks: string[] = [];
  if (xs.length > 1) {
    const count = Math.min(5, xs.length);
    for (let i = 0; i < count; i++) {
      const idx = Math.round((i / (count - 1)) * (xs.length - 1));
      ticks.push(xs[idx]!);
    }
  } else if (xs.length === 1) {
    ticks.push(xs[0]!);
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={width} height={height} role="img" aria-label="Line chart">
        <rect x={0} y={0} width={width} height={height} fill="transparent" />
        {/* Y axis grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={padding.top + innerH * (1 - t)}
              y2={padding.top + innerH * (1 - t)}
              stroke="rgba(255,255,255,0.08)"
            />
            <text
              x={padding.left - 6}
              y={padding.top + innerH * (1 - t) + 4}
              fontSize={10}
              textAnchor="end"
              fill="#94a3b8"
            >
              {(yMin + yRange * t).toFixed(1)}
            </text>
          </g>
        ))}
        {/* X ticks */}
        {ticks.map((t, i) => (
          <text
            key={i}
            x={xScale(t)}
            y={height - 6}
            fontSize={10}
            textAnchor="middle"
            fill="#94a3b8"
          >
            {t.length > 10 ? t.slice(5) : t}
          </text>
        ))}
        {xLabel && (
          <text
            x={padding.left + innerW / 2}
            y={height - 0}
            fontSize={10}
            textAnchor="middle"
            fill="#94a3b8"
          >
            {xLabel}
          </text>
        )}
        {yLabel && (
          <text
            transform={`translate(12, ${padding.top + innerH / 2}) rotate(-90)`}
            fontSize={10}
            textAnchor="middle"
            fill="#94a3b8"
          >
            {yLabel}
          </text>
        )}
        {series.map((s) => (
          <polyline
            key={s.name}
            fill="none"
            stroke={s.color}
            strokeWidth={2}
            points={s.points.map((p) => `${xScale(p.x)},${yScale(p.y)}`).join(" ")}
          />
        ))}
      </svg>
      <div style={{ marginTop: "4px", fontSize: "0.78rem", color: "#cbd5e1" }}>
        {series.map((s) => (
          <span key={s.name} style={{ marginRight: "12px" }}>
            <span
              style={{
                display: "inline-block",
                width: 10,
                height: 10,
                background: s.color,
                marginRight: 4,
                borderRadius: 2,
                verticalAlign: "middle",
              }}
            />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}