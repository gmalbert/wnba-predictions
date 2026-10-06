import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./AppShell";
import { Home } from "./pages/Home";
import { GamePredictions } from "./pages/GamePredictions";
import { ScenarioLab } from "./pages/ScenarioLab";
import { Standings } from "./pages/Standings";
import { TeamStats } from "./pages/TeamStats";
import { PlayerStats } from "./pages/PlayerStats";
import { ModelPerformance } from "./pages/ModelPerformance";
import { DataHealth } from "./pages/DataHealth";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Home />} />
          <Route path="/game-predictions" element={<GamePredictions />} />
          <Route path="/scenario-lab" element={<ScenarioLab />} />
          <Route path="/standings" element={<Standings />} />
          <Route path="/team-stats" element={<TeamStats />} />
          <Route path="/player-stats" element={<PlayerStats />} />
          <Route path="/model-performance" element={<ModelPerformance />} />
          <Route path="/data-health" element={<DataHealth />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}