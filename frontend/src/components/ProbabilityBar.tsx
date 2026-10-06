import React from "react";
import { WNBA_BLUE, WNBA_RED } from "../utils/format";

interface Props {
  homeProb: number | null;
  homeLabel: string;
  awayLabel: string;
  height?: number;
  fontSize?: number;
}

/** Faithful React port of the Streamlit `_prob_bar_html` snippets used in
 *  `predictions.py` and `pages/1_Game_Predictions.py`. The bar is split
 *  proportionally to `homeProb` (clamped to [0, 1]), with the home half in
 *  WNBA blue and the away half in WNBA red. The numeric percentages are
 *  rendered inside each half (white text).
 */
export function ProbabilityBar({ homeProb, homeLabel, awayLabel, height = 22, fontSize = 0.75 }: Props) {
  const safe = typeof homeProb === "number" && !Number.isNaN(homeProb)
    ? Math.min(Math.max(homeProb, 0), 1)
    : 0.5;
  const hp = Math.round(safe * 100);
  const ap = 100 - hp;
  return (
    <div style={{ width: "100%" }}>
      <div
        style={{
          display: "flex",
          height: `${height}px`,
          borderRadius: "6px",
          overflow: "hidden",
          fontSize: `${fontSize}rem`,
          fontWeight: 600,
        }}
      >
        <div
          style={{
            width: `${hp}%`,
            background: WNBA_BLUE,
            color: "white",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {hp}%
        </div>
        <div
          style={{
            width: `${ap}%`,
            background: WNBA_RED,
            color: "white",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {ap}%
        </div>
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: `${Math.max(fontSize - 0.05, 0.6)}rem`,
          color: "var(--muted-text, #888)",
          marginTop: "2px",
        }}
      >
        <span>{homeLabel}</span>
        <span>{awayLabel}</span>
      </div>
    </div>
  );
}