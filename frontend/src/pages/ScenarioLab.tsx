import React, { useCallback, useMemo, useState } from "react";
import { fetchReleaseGate, fetchScenarioPolicy } from "../api/dataClient";
import { MetricCard } from "../components/MetricCard";
import { StatusBanner } from "../components/StatusBanner";
import { useJson } from "../hooks/useJson";
import { ReleaseGatePayload, ScenarioPolicyPayload } from "../types/data";
import { simulateCorrelatedParlay, simulatePlayerProp, stakingPolicy } from "../utils/scenario";
import { pct } from "../utils/format";

const TABS = ["Player prop", "Parlay dependence", "Staking policy"] as const;
type Tab = typeof TABS[number];

export function ScenarioLab() {
  const [tab, setTab] = useState<Tab>("Player prop");
  const gate = useJson<ReleaseGatePayload>(useCallback(() => fetchReleaseGate(), []));
  const policy = useJson<ScenarioPolicyPayload>(useCallback(() => fetchScenarioPolicy(), []));

  return (
    <div>
      <h1>🧪 Scenario Lab</h1>
      <StatusBanner variant="error">
        Paper-only. Player props require minutes uncertainty; parlays use dependence simulation; Kelly is disabled.
      </StatusBanner>

      <div className="bo-tabs">
        {TABS.map((t) => (
          <div
            key={t}
            className={`bo-tab${t === tab ? " bo-tab-active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t}
          </div>
        ))}
      </div>

      {tab === "Player prop" && <PropTab />}
      {tab === "Parlay dependence" && <ParlayTab />}
      {tab === "Staking policy" && (
        <PolicyTab gate={gate.data} policy={policy.data} loading={policy.loading} />
      )}
    </div>
  );
}

function PropTab() {
  const [rate, setRate] = useState(0.65);
  const [rateSd, setRateSd] = useState(0.12);
  const [minutes, setMinutes] = useState(31);
  const [minutesSd, setMinutesSd] = useState(5);
  const [availability, setAvailability] = useState(0.85);
  const [line, setLine] = useState(19.5);

  const projection = useMemo(
    () =>
      simulatePlayerProp({
        rate_per_minute: rate,
        rate_sd: rateSd,
        minutes_mean: minutes,
        minutes_sd: minutesSd,
        availability_probability: availability,
        line,
      }),
    [rate, rateSd, minutes, minutesSd, availability, line],
  );

  return (
    <div>
      <p className="bo-info-text">
        This analytical calculator integrates the probability of playing and the player's minutes distribution.
      </p>
      <div className="bo-grid bo-grid-3">
        {/* Column order mirrors pages/2_Scenario_Lab.py st.columns(3):
            left = rate inputs, middle = minutes inputs, right = availability + line. */}
        <div className="bo-form-field">
          <label>Stat rate per minute</label>
          <input
            type="number"
            min={0}
            step={0.05}
            value={rate}
            onChange={(e) => setRate(Number(e.target.value))}
          />
        </div>
        <div className="bo-form-field">
          <label>Expected minutes if active</label>
          <input
            type="number"
            min={0}
            step={1}
            value={minutes}
            onChange={(e) => setMinutes(Number(e.target.value))}
          />
        </div>
        <div className="bo-form-field">
          <label>Availability probability: {availability.toFixed(2)}</label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={availability}
            onChange={(e) => setAvailability(Number(e.target.value))}
          />
        </div>
        <div className="bo-form-field">
          <label>Rate SD</label>
          <input
            type="number"
            min={0.01}
            step={0.01}
            value={rateSd}
            onChange={(e) => setRateSd(Number(e.target.value))}
          />
        </div>
        <div className="bo-form-field">
          <label>Minutes SD</label>
          <input
            type="number"
            min={0.5}
            step={0.5}
            value={minutesSd}
            onChange={(e) => setMinutesSd(Number(e.target.value))}
          />
        </div>
        <div className="bo-form-field">
          <label>Prop line</label>
          <input
            type="number"
            min={0}
            step={0.5}
            value={line}
            onChange={(e) => setLine(Number(e.target.value))}
          />
        </div>
      </div>

      <div className="bo-grid bo-grid-3" style={{ marginTop: 16 }}>
        <MetricCard label="Projected mean" value={projection.mean.toFixed(1)} />
        <MetricCard label="Over probability" value={pct(projection.over_probability, 1)} />
        <MetricCard label="Under probability" value={pct(projection.under_probability, 1)} />
      </div>

      {projection.status === "no_bet" && (
        <StatusBanner variant="warning">No bet: {projection.reason}</StatusBanner>
      )}
    </div>
  );
}

function ParlayTab() {
  const [legs, setLegs] = useState<[number, number, number]>([0.58, 0.56, 0.54]);
  const [correlation, setCorrelation] = useState(0.25);

  const matrix = useMemo(() => {
    const m = [
      [1, correlation, correlation],
      [correlation, 1, correlation],
      [correlation, correlation, 1],
    ];
    return m;
  }, [correlation]);

  const result = useMemo(
    () => simulateCorrelatedParlay(legs, matrix),
    [legs, matrix],
  );

  return (
    <div>
      <p className="bo-info-text">
        Positive correlation can materially change a multi-leg probability; independence is shown only as a comparator.
      </p>
      <div className="bo-grid bo-grid-3">
        <div className="bo-form-field">
          <label>Leg 1 probability: {legs[0].toFixed(2)}</label>
          <input
            type="range"
            min={0.05}
            max={0.95}
            step={0.01}
            value={legs[0]}
            onChange={(e) => setLegs([Number(e.target.value), legs[1], legs[2]])}
          />
        </div>
        <div className="bo-form-field">
          <label>Leg 2 probability: {legs[1].toFixed(2)}</label>
          <input
            type="range"
            min={0.05}
            max={0.95}
            step={0.01}
            value={legs[1]}
            onChange={(e) => setLegs([legs[0], Number(e.target.value), legs[2]])}
          />
        </div>
        <div className="bo-form-field">
          <label>Leg 3 probability: {legs[2].toFixed(2)}</label>
          <input
            type="range"
            min={0.05}
            max={0.95}
            step={0.01}
            value={legs[2]}
            onChange={(e) => setLegs([legs[0], legs[1], Number(e.target.value)])}
          />
        </div>
      </div>
      <div className="bo-form-field" style={{ marginTop: 12, maxWidth: 600 }}>
        <label>Shared game/roster correlation: {correlation.toFixed(2)}</label>
        <input
          type="range"
          min={-0.5}
          max={0.9}
          step={0.05}
          value={correlation}
          onChange={(e) => setCorrelation(Number(e.target.value))}
        />
      </div>

      <div className="bo-grid bo-grid-3" style={{ marginTop: 16 }}>
        <MetricCard label="Simulated joint hit" value={pct(result.joint_probability, 2)} />
        <MetricCard label="Independence estimate" value={pct(result.independent_probability, 2)} />
        <MetricCard
          label="Dependence adjustment"
          value={`${result.dependence_lift >= 0 ? "+" : ""}${(result.dependence_lift * 100).toFixed(2)}%`}
        />
      </div>
    </div>
  );
}

function PolicyTab({
  gate,
  policy,
  loading,
}: {
  gate: ReleaseGatePayload | null;
  policy: ScenarioPolicyPayload | null;
  loading: boolean;
}) {
  const livePolicy = stakingPolicy(Boolean(gate?.passed));
  return (
    <div>
      <pre
        style={{
          background: "var(--card-bg-alt)",
          padding: 12,
          borderRadius: 6,
          overflow: "auto",
          fontSize: "0.9rem",
        }}
      >
{JSON.stringify(policy ?? livePolicy, null, 2)}
      </pre>
      {loading && !policy && (
        <p className="bo-info-text">Loading policy from pipeline…</p>
      )}
      <p className="bo-info-text" style={{ marginTop: 8 }}>
        Season-futures simulation is available in <code>utils.market_simulation.simulate_season_futures</code> for pipeline use.
      </p>
    </div>
  );
}