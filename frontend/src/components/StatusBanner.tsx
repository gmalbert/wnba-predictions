import React from "react";

type Variant = "info" | "warning" | "error" | "success";

interface Props {
  variant: Variant;
  children: React.ReactNode;
}

const STYLES: Record<Variant, React.CSSProperties> = {
  info: {
    background: "rgba(59, 130, 246, 0.12)",
    borderLeft: "4px solid #3b82f6",
    color: "#cbd5e1",
  },
  warning: {
    background: "rgba(217, 119, 6, 0.14)",
    borderLeft: "4px solid #d97706",
    color: "#fde68a",
  },
  error: {
    background: "rgba(153, 27, 27, 0.18)",
    borderLeft: "4px solid #b91c1c",
    color: "#fecaca",
  },
  success: {
    background: "rgba(22, 163, 74, 0.14)",
    borderLeft: "4px solid #16a34a",
    color: "#bbf7d0",
  },
};

export function StatusBanner({ variant, children }: Props) {
  return (
    <div
      role={variant === "error" || variant === "warning" ? "alert" : "status"}
      style={{
        padding: "10px 14px",
        borderRadius: "0.4rem",
        marginBottom: "12px",
        fontSize: "0.92rem",
        ...STYLES[variant],
      }}
    >
      {children}
    </div>
  );
}