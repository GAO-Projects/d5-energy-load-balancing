"use client";

import React, { useEffect, useState } from "react";

interface ChannelTelemetry {
  asset_name: string;
  sensor_mac: string;
  sequence: number;
  voltage_v: number;
  current_a: number;
  watts: number;
  duty_pct: number;
  rssi: number;
  quality_flag: string;
}

interface TelemetryFrame {
  timestamp: number;
  hardware_mode: string;
  demo_track: "physical_ai" | "aiot";
  budget_watts: number;
  data_age_s: number;
  decision: {
    decision_id: string;
    system_state: string;
    reason_code: string;
    measured_total_watts: number;
    forecast_5s_watts: number;
    forecast_10s_watts: number;
    error_margin_watts: number;
    target_duties: Record<string, number>;
    anomaly_score: number;
    command_id: string | null;
    ack_status: string;
  };
  channels: Record<string, ChannelTelemetry>;
}

export default function EnergyLoadBalancingDashboard() {
  const [frame, setFrame] = useState<TelemetryFrame | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [budgetInput, setBudgetInput] = useState<number>(8.0);
  const [extraDemand, setExtraDemand] = useState<boolean>(false);
  const [bleFault, setBleFault] = useState<boolean>(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/telemetry";

  useEffect(() => {
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);
    ws.onmessage = (event) => {
      const parsed: TelemetryFrame = JSON.parse(event.data);
      setFrame(parsed);
    };
    return () => ws.close();
  }, [wsUrl]);

  const sendControlUpdate = async (patch: Record<string, unknown>) => {
    await fetch(`${apiUrl}/api/control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
  };

  const stateColor = (state?: string) => {
    switch (state) {
      case "OPTIMAL":
        return "bg-emerald-500/20 text-emerald-300 border-emerald-500";
      case "SHEDDING":
        return "bg-amber-500/20 text-amber-300 border-amber-500";
      case "INFEASIBLE_BUDGET":
      case "STALE_FALLBACK":
        return "bg-rose-500/20 text-rose-300 border-rose-500";
      default:
        return "bg-sky-500/20 text-sky-300 border-sky-500";
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-6 font-sans">
      {/* Top Header */}
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            D5: AI Decision for Energy Load Balancing
          </h1>
          <p className="text-sm text-slate-400">
            GAO 217030 BLE-to-MQTT Gateway &bull; Ridge Demand Forecast &bull; Priority PWM Actuation
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`px-3 py-1 rounded-full text-xs font-semibold border ${
              wsConnected
                ? "bg-emerald-950 text-emerald-300 border-emerald-700"
                : "bg-rose-950 text-rose-300 border-rose-700"
            }`}
          >
            {wsConnected ? "LIVE STREAM (1 Hz)" : "DISCONNECTED"}
          </span>
          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-sky-300 border border-slate-700 uppercase">
            Source: {frame?.hardware_mode || "SYNTHETIC"}
          </span>
        </div>
      </header>

      {/* Simulator & Grid Budget Control Strip */}
      <section className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-6 bg-slate-900/90 border border-slate-800 rounded-xl p-4">
        <div>
          <label className="block text-xs font-semibold uppercase text-amber-400 mb-1">
            Simulated Grid Budget: {budgetInput.toFixed(1)} W
          </label>
          <input
            type="range"
            min={3.0}
            max={13.0}
            step={0.5}
            value={budgetInput}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              setBudgetInput(val);
              sendControlUpdate({ budget_watts: val });
            }}
            className="w-full accent-amber-400 cursor-pointer"
          />
          <div className="flex justify-between text-[11px] text-slate-400 mt-1">
            <span>3.0 W (Infeasible)</span>
            <span>8.0 W (Curtail)</span>
            <span>13.0 W (Full)</span>
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase text-slate-400 mb-1">
            Demonstration Track
          </label>
          <div className="flex gap-2">
            <button
              onClick={() => sendControlUpdate({ demo_track: "physical_ai" })}
              className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold border transition ${
                frame?.demo_track !== "aiot"
                  ? "bg-teal-600 border-teal-400 text-white"
                  : "bg-slate-800 border-slate-700 text-slate-300"
              }`}
            >
              Physical AI (Closed-Loop)
            </button>
            <button
              onClick={() => sendControlUpdate({ demo_track: "aiot" })}
              className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold border transition ${
                frame?.demo_track === "aiot"
                  ? "bg-sky-600 border-sky-400 text-white"
                  : "bg-slate-800 border-slate-700 text-slate-300"
              }`}
            >
              AIoT (Passive Monitor)
            </button>
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase text-slate-400 mb-1">
            Operator Load Switch (Simulated)
          </label>
          <button
            onClick={() => {
              const next = !extraDemand;
              setExtraDemand(next);
              sendControlUpdate({ extra_demand_switch: next });
            }}
            className={`w-full py-2 px-3 rounded-lg text-xs font-bold border transition ${
              extraDemand
                ? "bg-amber-600 border-amber-400 text-white"
                : "bg-slate-800 border-slate-700 text-slate-300"
            }`}
          >
            {extraDemand ? "EXTRA LOAD: ON (+2.2 W)" : "EXTRA LOAD: OFF (Normal)"}
          </button>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase text-slate-400 mb-1">
            Fault Injection Test
          </label>
          <button
            onClick={() => {
              const next = !bleFault;
              setBleFault(next);
              sendControlUpdate({ fault_ble_dropout: next });
            }}
            className={`w-full py-2 px-3 rounded-lg text-xs font-bold border transition ${
              bleFault
                ? "bg-rose-600 border-rose-400 text-white"
                : "bg-slate-800 border-slate-700 text-slate-300"
            }`}
          >
            {bleFault ? "FAULT ACTIVE: BLE DROPOUT" : "INJECT BLE DROPOUT (>2s)"}
          </button>
        </div>
      </section>

      {/* Primary KPI Cards */}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-xs uppercase text-slate-400 font-semibold">Measured Total Power</p>
          <p className="text-3xl font-bold text-white mt-1">
            {frame ? `${frame.decision.measured_total_watts.toFixed(2)} W` : "--"}
          </p>
          <p className="text-xs text-slate-400 mt-1">
            Budget Limit: <span className="text-amber-300 font-semibold">{frame?.budget_watts.toFixed(1)} W</span>
          </p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-xs uppercase text-slate-400 font-semibold">AI 10s Demand Forecast</p>
          <p className="text-3xl font-bold text-sky-400 mt-1">
            {frame ? `${frame.decision.forecast_10s_watts.toFixed(2)} W` : "--"}
          </p>
          <p className="text-xs text-slate-400 mt-1">
            Safety Margin: &plusmn;{frame?.decision.error_margin_watts.toFixed(2)} W (Ridge)
          </p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-xs uppercase text-slate-400 font-semibold">Policy Decision State</p>
          <div className="mt-2">
            <span className={`px-3 py-1 rounded-md text-sm font-bold border ${stateColor(frame?.decision.system_state)}`}>
              {frame?.decision.system_state || "INITIALIZING"}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-2 truncate">{frame?.decision.reason_code}</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-xs uppercase text-slate-400 font-semibold">Telemetry Freshness & Anomaly</p>
          <p className="text-3xl font-bold text-emerald-400 mt-1">
            {frame ? `${frame.data_age_s.toFixed(1)} s` : "--"}
          </p>
          <p className="text-xs text-slate-400 mt-1">
            Anomaly Score: {frame ? frame.decision.anomaly_score.toFixed(2) : "--"}
          </p>
        </div>
      </section>

      {/* Channel Load Allocation & Closed-Loop Feedback */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {["1", "2", "3"].map((chKey) => {
          const ch = frame?.channels?.[chKey];
          const priorityTag =
            chKey === "1"
              ? "PRIORITY 1: ESSENTIAL"
              : chKey === "2"
              ? "PRIORITY 2: FLEXIBLE"
              : "PRIORITY 3: SHED FIRST";
          const barColor =
            chKey === "1" ? "bg-emerald-500" : chKey === "2" ? "bg-sky-500" : "bg-amber-500";

          return (
            <div key={chKey} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                  {priorityTag}
                </span>
                <span className="text-xs font-mono text-slate-400">{ch?.sensor_mac || "WAITING"}</span>
              </div>
              <h2 className="text-lg font-bold text-white">{ch?.asset_name || `Channel ${chKey}`}</h2>
              <div className="flex items-baseline justify-between mt-3">
                <span className="text-2xl font-bold text-white">
                  {ch ? `${ch.watts.toFixed(2)} W` : "0.00 W"}
                </span>
                <span className="text-sm font-semibold text-teal-300">
                  PWM Duty: {ch ? `${ch.duty_pct}%` : "--"}
                </span>
              </div>
              <div className="w-full bg-slate-800 h-3 rounded-full overflow-hidden mt-2">
                <div
                  className={`h-full transition-all duration-300 ${barColor}`}
                  style={{ width: `${ch ? ch.duty_pct : 0}%` }}
                />
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs text-slate-400 mt-3 pt-2 border-t border-slate-800">
                <div>Bus: {ch ? `${ch.voltage_v.toFixed(2)}V` : "--"}</div>
                <div>Curr: {ch ? `${ch.current_a.toFixed(3)}A` : "--"}</div>
                <div>Seq: #{ch?.sequence ?? "--"}</div>
              </div>
            </div>
          );
        })}
      </section>

      {/* Audit & Command Trace Footer */}
      <section className="bg-slate-900 border border-slate-800 rounded-xl p-4 font-mono text-xs text-slate-300">
        <div className="flex flex-wrap justify-between gap-2">
          <span>
            <strong className="text-slate-400">DECISION ID:</strong> {frame?.decision.decision_id || "--"}
          </span>
          <span>
            <strong className="text-slate-400">SERIAL CMD ID:</strong> {frame?.decision.command_id || "NONE"}
          </span>
          <span>
            <strong className="text-slate-400">CONTROLLER ACK:</strong>{" "}
            <span className="text-emerald-400">{frame?.decision.ack_status || "--"}</span>
          </span>
        </div>
      </section>
    </main>
  );
}
