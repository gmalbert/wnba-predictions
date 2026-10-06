import React from "react";

/** Mirrors the Streamlit `footer.add_betting_oracle_footer()` block. */
export function Footer() {
  return (
    <footer
      style={{
        textAlign: "center",
        padding: "20px 0",
        borderTop: "1px solid #e0e0e0",
        marginTop: "40px",
        color: "#cbd5e1",
        fontFamily: "sans-serif",
      }}
    >
      <p style={{ margin: "0 0 10px 0", fontSize: 14 }}>
        Powered by{" "}
        <a
          href="https://www.betting-oracle.com"
          target="_blank"
          rel="noreferrer noopener"
          style={{ color: "#3b82f6", textDecoration: "none", fontWeight: 700 }}
        >
          Betting Oracle
        </a>
      </p>
      <p style={{ margin: "0 0 15px 0", fontSize: 12, color: "#94a3b8" }}>
        Sports Prediction Analytics
      </p>
      <a href="https://www.betting-oracle.com" target="_blank" rel="noreferrer noopener">
        <img
          src="./betting-oracle-logo.png"
          alt="Betting Oracle Logo"
          style={{ height: 60, width: "auto", border: "none" }}
        />
      </a>
    </footer>
  );
}