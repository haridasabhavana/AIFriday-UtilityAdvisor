"use client";

import React, { useEffect, useState } from "react";
import { LoadProfileChart } from "./components";
import { apiGet, apiPost } from "./lib";

export default function HomePage() {
  const [tab, setTab] = useState<"customer" | "admin">("customer");
  const [customers, setCustomers] = useState<any[]>([]);
  const [custRef, setCustRef] = useState("C001");
  const [dash, setDash] = useState<any>(null);
  const [simResult, setSimResult] = useState<any>(null);
  const [uploadMsg, setUploadMsg] = useState("");

  // Simulator controls per Decision D-9 (no AC setpoint)
  const [shiftPct, setShiftPct] = useState(0);
  const [acHours, setAcHours] = useState(0);
  const [standbyPct, setStandbyPct] = useState(0);
  const [appShift, setAppShift] = useState<Record<string, string>>({});

  // Chat state
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<any[]>([]);
  const [adminData, setAdminData] = useState<any>(null);

  useEffect(() => {
    apiGet<any[]>("/customers").then((list) => {
      setCustomers(list);
      if (list.length) setCustRef(list[0].cust_ref);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!custRef) return;
    apiGet<any>(`/dashboard/${custRef}`).then((d) => {
      setDash(d);
      setSimResult(null);
      setShiftPct(0);
      setAcHours(0);
      setStandbyPct(0);
      setAppShift({});
    }).catch(() => {});
  }, [custRef]);

  function buildActions(nextShiftPct = shiftPct, nextAc = acHours, nextStandby = standbyPct, nextApp = appShift) {
    const actions: any[] = [];
    if (nextShiftPct > 0) actions.push({ type: "shift_load", pct: nextShiftPct });
    if (nextAc > 0) actions.push({ type: "ac_hours", hours: nextAc });
    if (nextStandby > 0) actions.push({ type: "reduce_load", pct: nextStandby });
    Object.entries(nextApp).forEach(([appId, win]) => {
      if (win && win !== "peak") {
        actions.push({ type: "shift_kwh", appliance_id: appId, from_window: "peak", to_window: win });
      }
    });
    return actions;
  }

  async function runSim(nextShiftPct = shiftPct, nextAc = acHours, nextStandby = standbyPct, nextApp = appShift) {
    const actions = buildActions(nextShiftPct, nextAc, nextStandby, nextApp);
    const res = await apiPost<any>("/simulate", { cust_ref: custRef, actions });
    setSimResult(res);
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`/api/upload?cust_ref=${encodeURIComponent(custRef)}`, { method: "POST", body: form });
    const data = await res.json();
    if (res.ok) {
      setUploadMsg(`Uploaded for ${data.cust_ref}: ${data.valid_count}/${data.raw_count} valid, quality ${data.quality_score}%`);
      const d = await apiGet<any>(`/dashboard/${data.cust_ref}`);
      setDash(d);
    } else {
      setUploadMsg(`Upload error: ${data.detail}`);
    }
  }

  async function askChat(q: string) {
    if (!q.trim()) return;
    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setQuestion("");
    const res = await apiPost<any>("/chat", { cust_ref: custRef, question: q, actions: buildActions() });
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        text: res.reply,
        meta: `${res.mode} • grounded=${res.grounding?.grounded} • tools=[${(res.tool_calls || []).join(", ")}]`,
      },
    ]);
  }

  async function loadAdmin() {
    setTab("admin");
    const [agg, docs, audit] = await Promise.all([
      apiGet<any>("/admin/aggregates"),
      apiGet<any[]>("/admin/documents"),
      apiGet<any[]>("/admin/audit"),
    ]);
    setAdminData({ agg, docs, audit });
  }

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3 bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div>
          <h1 className="text-lg font-bold">EnergyWise AI <span className="text-emerald-600">Option B</span></h1>
          <p className="text-xs text-slate-500">TAR-ILL-001 (Peak 18:00–22:00 ₹10.20/kWh) • MCP Tool-Calling + Grounding</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select className="text-xs border rounded-lg px-2.5 py-1.5" value={custRef} onChange={(e) => setCustRef(e.target.value)}>
            {customers.map((c) => (
              <option key={c.cust_ref} value={c.cust_ref}>{c.cust_ref} — {c.segment}</option>
            ))}
          </select>
          <label className="text-xs font-semibold bg-emerald-600 text-white px-3 py-1.5 rounded-lg cursor-pointer">
            Upload CSV
            <input type="file" accept=".csv" className="hidden" onChange={handleUpload} />
          </label>
          <button onClick={() => setTab("customer")} className={`text-xs px-3 py-1.5 rounded-lg font-semibold ${tab === "customer" ? "bg-slate-900 text-white" : "bg-slate-100"}`}>
            Customer
          </button>
          <button onClick={loadAdmin} className={`text-xs px-3 py-1.5 rounded-lg font-semibold ${tab === "admin" ? "bg-slate-900 text-white" : "bg-slate-100"}`}>
            Admin & Audit
          </button>
        </div>
      </header>

      {uploadMsg && <div className="text-xs bg-emerald-50 border border-emerald-200 text-emerald-800 px-3 py-2 rounded-xl">{uploadMsg}</div>}

      {tab === "customer" && dash && (
        <>
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-2xl border border-slate-200">
              <div className="text-xs text-slate-500">Consumption ({dash.summary.day_count}d)</div>
              <div className="text-2xl font-bold mt-1">{simResult ? simResult.simulation.scenario.kwh : dash.summary.total_kwh} kWh</div>
              <div className="text-[11px] text-slate-500">Quality score: {dash.summary.quality_score}%</div>
            </div>
            <div className="bg-white p-4 rounded-2xl border border-slate-200">
              <div className="text-xs text-slate-500">Estimated Cost</div>
              <div className="text-2xl font-bold text-emerald-600 mt-1">₹{simResult ? simResult.simulation.scenario.cost_inr : dash.summary.est_cost_inr}</div>
              <div className="text-[11px] text-slate-500">Next mo forecast: ₹{simResult ? simResult.forecast.next_month_cost_inr : dash.forecast.next_month_cost_inr}</div>
            </div>
            <div className="bg-white p-4 rounded-2xl border border-slate-200">
              <div className="text-xs text-slate-500">Peak Share (18–22h)</div>
              <div className="text-2xl font-bold mt-1">{dash.summary.peak_share_pct}%</div>
              <div className="text-[11px] text-slate-500">Baseload: {dash.summary.baseload_kw} kW</div>
            </div>
            <div className="bg-emerald-700 text-white p-4 rounded-2xl">
              <div className="text-xs text-emerald-100">Scenario Delta (Cost / CO₂)</div>
              <div className="text-2xl font-bold mt-1">{simResult ? `₹${simResult.simulation.delta.cost_inr}` : "₹0"}</div>
              <div className="text-[11px] text-emerald-100">{simResult ? `${simResult.simulation.delta.co2_kg} kg CO₂` : "Adjust controls below"}</div>
            </div>
          </section>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-7 space-y-6">
              <div className="bg-white p-5 rounded-2xl border border-slate-200">
                <h2 className="text-sm font-semibold mb-3">24-Hour Load Profile (Baseline vs. Scenario)</h2>
                <LoadProfileChart baseline={dash.summary.hourly_avg} scenario={simResult?.simulation?.hourly_scenario} />
              </div>

              <div className="bg-white p-5 rounded-2xl border border-slate-200 space-y-4">
                <h2 className="text-sm font-semibold">What-If Simulator (D-9 Controls)</h2>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                  <div>
                    <label className="font-semibold">Shift Peak → Night: {shiftPct}%</label>
                    <input type="range" min={0} max={50} step={5} value={shiftPct} className="w-full"
                      onChange={(e) => { const v = Number(e.target.value); setShiftPct(v); runSim(v, acHours, standbyPct, appShift); }} />
                  </div>
                  <div>
                    <label className="font-semibold">AC Runtime Trim: {acHours}h</label>
                    <input type="range" min={0} max={4} step={0.5} value={acHours} className="w-full"
                      onChange={(e) => { const v = Number(e.target.value); setAcHours(v); runSim(shiftPct, v, standbyPct, appShift); }} />
                  </div>
                  <div>
                    <label className="font-semibold">Standby Cut: {standbyPct}%</label>
                    <input type="range" min={0} max={30} step={5} value={standbyPct} className="w-full"
                      onChange={(e) => { const v = Number(e.target.value); setStandbyPct(v); runSim(shiftPct, acHours, v, appShift); }} />
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {(dash.appliances || []).map((a: any) => (
                    <div key={a.id} className="border rounded-xl p-2.5 text-xs">
                      <div className="font-semibold">{a.name}</div>
                      <div className="text-[11px] text-slate-500 mb-1">Est. {a.monthly_kwh} kWh/mo</div>
                      <select className="w-full border rounded px-1.5 py-1" value={appShift[a.id] || "peak"}
                        onChange={(e) => { const n = { ...appShift, [a.id]: e.target.value }; setAppShift(n); runSim(shiftPct, acHours, standbyPct, n); }}>
                        <option value="peak">Peak (18–22h)</option>
                        <option value="off_peak">Off-Peak (23–06h)</option>
                        <option value="standard">Standard (06–18h)</option>
                      </select>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="lg:col-span-5 space-y-6">
              <div className="bg-white p-5 rounded-2xl border border-slate-200 space-y-3">
                <h2 className="text-sm font-semibold">Recommendation Candidates</h2>
                {dash.recommendations.map((r: any) => (
                  <div key={r.id} className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1">
                    <div className="flex justify-between font-semibold">
                      <span>{r.action}</span>
                      <span className="text-emerald-700">₹{r.inr_saving}/mo</span>
                    </div>
                    <div className="text-slate-500">{r.pattern} • Confidence: {r.confidence}</div>
                  </div>
                ))}
              </div>

              <div className="bg-white p-5 rounded-2xl border border-slate-200">
                <h2 className="text-sm font-semibold mb-2">Grounded Advisor Chat</h2>
                <div className="space-y-2 max-h-56 overflow-y-auto mb-3 text-xs">
                  {messages.map((m, i) => (
                    <div key={i} className={m.role === "user" ? "bg-emerald-600 text-white p-2.5 rounded-xl ml-8" : "bg-slate-100 p-2.5 rounded-xl mr-4"}>
                      <div>{m.text}</div>
                      {m.meta && <div className="text-[10px] text-slate-500 mt-1">{m.meta}</div>}
                    </div>
                  ))}
                </div>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  <button onClick={() => askChat("Why is my bill high?")} className="text-[11px] bg-slate-100 px-2.5 py-1 rounded-full">Why is my bill high?</button>
                  <button onClick={() => askChat("How much do I save in my simulation?")} className="text-[11px] bg-slate-100 px-2.5 py-1 rounded-full">Explain simulation</button>
                  <button onClick={() => askChat("What is my next month forecast?")} className="text-[11px] bg-slate-100 px-2.5 py-1 rounded-full">Next month forecast</button>
                  <button onClick={() => askChat("Can you issue a refund on my bill?")} className="text-[11px] bg-slate-100 px-2.5 py-1 rounded-full">Unsupported question</button>
                </div>
                <form onSubmit={(e) => { e.preventDefault(); askChat(question); }} className="flex gap-2">
                  <input className="flex-1 border rounded-xl px-3 py-1.5 text-xs" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask EnergyWise AI..." />
                  <button className="bg-emerald-600 text-white px-3 py-1.5 rounded-xl text-xs font-semibold" type="submit">Ask</button>
                </form>
              </div>
            </div>
          </div>
        </>
      )}

      {tab === "admin" && adminData && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white p-5 rounded-2xl border border-slate-200 text-xs space-y-3">
            <h2 className="text-sm font-semibold">Demand Response Segment Aggregates</h2>
            {adminData.agg.segments.map((s: any) => (
              <div key={s.segment} className="flex justify-between border-b pb-2">
                <span>{s.segment}</span>
                <span>{s.meters} meters • Avg quality {s.avg_quality}%</span>
              </div>
            ))}
          </div>
          <div className="bg-white p-5 rounded-2xl border border-slate-200 text-xs space-y-2">
            <h2 className="text-sm font-semibold">Approved KB Documents ({adminData.docs.length})</h2>
            {adminData.docs.map((d: any) => (
              <div key={d.source} className="border-b pb-2">
                <div className="font-semibold">{d.doc_id || d.source} ({d.doc_type})</div>
                <div className="text-slate-500">v{d.version} • {d.status} • Approved by {d.approved_by}</div>
              </div>
            ))}
          </div>
          <div className="bg-white p-5 rounded-2xl border border-slate-200 text-xs space-y-2 lg:col-span-2">
            <h2 className="text-sm font-semibold">Recent AI & Grounding Audit Log ({adminData.audit.length})</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b text-slate-500">
                    <th className="py-1.5 pr-3">Cust Ref</th>
                    <th className="py-1.5 px-3">Action</th>
                    <th className="py-1.5 px-3">Grounding</th>
                    <th className="py-1.5 pl-3">Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {adminData.audit.slice(0, 8).map((a: any) => (
                    <tr key={a.id} className="border-b">
                      <td className="py-1.5 pr-3 font-mono">{a.cust_ref}</td>
                      <td className="py-1.5 px-3">{a.action}</td>
                      <td className="py-1.5 px-3 font-mono text-[11px]">{a.grounding_json}</td>
                      <td className="py-1.5 pl-3 text-slate-500">{a.created_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
