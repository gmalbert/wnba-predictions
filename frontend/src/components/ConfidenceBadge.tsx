import React from "react";
import { CONF_COLORS } from "../utils/format";

interface Props {
  tier: "High" | "Medium" | "Low" | string;
}

/** Reproduces the `_conf_badge` HTML used on the Streamlit Home page. */
export function ConfidenceBadge({ tier }: Props) {
  const color = CONF_COLORS[tier] ?? CONF_COLORS.Low;
  return (
    <span
      style={{
        background: color,
        color: "white",
        padding: "1px 9px",
        borderRadius: "10px",
        fontSize: "0.72rem",
        fontWeight: 700,
        display: "inline-block",
      }}
    >
      {tier}
    </span>
  );
}

export function NoBetBadge() {
  return (
    <span
      style={{
        background: "#991b1b",
        color: "white",
        padding: "2px 9px",
        borderRadius: "10px",
        fontSize: "0.72rem",
        fontWeight: 700,
        display: "inline-block",
        letterSpacing: "0.04em",
      }}
    >
      NO BET · PAPER ONLY
    </span>
  );
}