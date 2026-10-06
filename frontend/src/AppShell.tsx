import React from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Footer } from "./components/Footer";

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

interface NavGroup {
  label?: string;
  items: NavItem[];
}

const NAV: NavGroup[] = [
  {
    items: [{ to: "/", label: "Home", icon: "🏠" }],
  },
  {
    label: "Predictions",
    items: [
      { to: "/game-predictions", label: "Game Predictions", icon: "🏀" },
      { to: "/scenario-lab", label: "Scenario Lab", icon: "🧪" },
    ],
  },
  {
    label: "Stats",
    items: [
      { to: "/standings", label: "Standings", icon: "🏆" },
      { to: "/team-stats", label: "Team Stats", icon: "📊" },
      { to: "/player-stats", label: "Player Stats", icon: "👤" },
    ],
  },
  {
    label: "Models",
    items: [
      { to: "/model-performance", label: "Model Performance", icon: "📈" },
      { to: "/data-health", label: "Data Health", icon: "🩺" },
    ],
  },
];

export function AppShell() {
  const { pathname } = useLocation();
  const showSidebarLogo = pathname !== "/";
  return (
    <div className="bo-app">
      <aside className="bo-sidebar" aria-label="Primary navigation">
        <nav>
          {NAV.map((group, g) => (
            <div key={g} style={{ marginBottom: "12px" }}>
              {group.label && (
                <div className="bo-nav-group-label">{group.label}</div>
              )}
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `bo-nav-link${isActive ? " bo-nav-link-active" : ""}`
                  }
                >
                  <span className="bo-nav-icon">{item.icon}</span>
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        {showSidebarLogo && (
          <div className="bo-sidebar-logo">
            <img src="./logo_no_words.png" alt="WNBA" width={120} />
          </div>
        )}
      </aside>
      <main className="bo-main">
        <Outlet />
        <Footer />
      </main>
    </div>
  );
}