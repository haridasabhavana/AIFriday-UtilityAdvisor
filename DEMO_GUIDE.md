# EnergyWise AI — Option B PoC Judging Presentation & Freeze Guide

## 1. Quick Startup & Database Reset Commands (Clean Restart)

**Reset / Initialise Clean Synthetic Database (100 customers × 90 days):**
```powershell
python -m energywise.data.generate
python -m energywise.ingest.ingest
```

**Terminal 1 — FastAPI Backend (port 8000):**
```powershell
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — Next.js 15 UI (port 3000):**
```cmd
cd web
set NODE_OPTIONS=--use-system-ca
npm run dev
```

Open **http://localhost:3000**.

---

## 2. 60-Second Business Problem & Solution Introduction

> "Utilities collect millions of hourly smart-meter readings, yet customers only see a single monthly bill—they don't know *when* they are paying peak rates or *how* to save. Meanwhile, giving raw customer data directly to a generative AI model risks hallucinated savings and privacy leaks.
>
> **EnergyWise AI (Option B)** solves both problems. Plain, deterministic Python engines compute every single kWh, rupee, peak share, forecast, and CO₂ figure. An AI agent calls those engines over **MCP (Model Context Protocol)**, passes through an outbound **privacy scanner** and a **PII vault**, and a **number-level grounding validator** checks every number in the AI's reply against the engine outputs before the customer sees it. If the LLM gateway is ever offline, it automatically switches to deterministic **Rules Mode** with zero downtime."

---

## 3. Architecture Explanation (For Technical Jury)

- **UI (`web/`, Next.js 15 + Tailwind, port 3000):** Responsive customer & admin workspace calling FastAPI over `/api/*`.
- **API (`api/main.py`, FastAPI, port 8000):** Serves dashboard, simulator, CSV upload, and admin endpoints; dashboard/simulator sliders bypass the LLM and call deterministic engines directly.
- **Deterministic Engines (`energywise/engines/tools.py`):** Authoritative math for `TAR-ILL-001` billing, recommendations, what-if simulation, statistical forecast, and CO₂ (`0.82 kg/kWh`).
- **MCP & AI Agent (`energywise/mcp_servers/` + `energywise/agent/`):** FastMCP stdio servers (`engines_server.py`, `kb_server.py`, `smart_meter_server.py`), tool-calling loop, `privacy.scan()`, `grounding.check()`, and `rules_mode` fallback.
- **Privacy Vault & Audit (`data/pii_vault.db` + `data/energywise.db`):** `meter_id → cust_ref` (`C001`–`C100`) pseudonymisation at ingestion; AI and MCP servers never open `pii_vault.db`; all AI/grounding events are logged to `audit`.

---

## 4. Data & Journey Distinction: `C001` (90-Day) vs. `C098` (3-Row CSV Upload)

- **Main Dashboard & Simulation (`C001`):** Uses the pre-ingested **90-day hourly synthetic dataset** (30-day active window = `478.26 kWh`, `₹3,926.82` under `TAR-ILL-001`, `35.0%` Peak `18:00–22:00`, `99.9%` quality score).
- **CSV Upload Demonstration (`C098`):** Demonstrates live CSV ingestion (`POST /upload`) on a separate synthetic profile (`C098`) with a small 3-row sample file (`timestamp`/`consumption_kwh` aliases) so `C001`'s 90-day baseline remains intact for the rest of the walkthrough.

---

## 5. Independently Verified Simulation Scenario (`C001`)

- **Controls Applied:** **Shift Peak → Night = `20%`** + **AC Runtime Trim = `1.0 hr/day`**.
- **Baseline (30d):** `478.26 kWh` | **`₹3,926.82`** | `167.22 peak kWh` | `392.18 kg CO₂`
- **Simulated (30d):** `442.26 kWh` | **`₹3,419.16`** | `97.78 peak kWh` | `362.66 kg CO₂`
- **Exact Delta:** **`-36.0 kWh`** (`1.0 hr/day × 1.2 kW × 30 days`) | **`-₹507.66`** (`3926.82 - 3419.16 = 507.66`) | **`-29.52 kg CO₂`** (`-36.0 × 0.82 = -29.52`)

---

## 6. Measurement vs. Estimate vs. Modelled Distinction

1. **Measured Consumption:** `478.26 kWh` and `₹3,926.82` come from `C001`'s hourly smart-meter readings.
2. **Estimated Appliance Figures:** Appliance dropdowns (e.g., Washing Machine `36 kWh/mo`) are customer-declared/benchmark estimates, not sub-metered sensors.
3. **Modelled Forecasts & Scenarios:** What-if deltas and next-month forecasts (`FR-09`) are deterministic projections, not guaranteed savings.

---

## 7. Rules Mode vs. Live LLM Gateway Mode

- **Live LLM Mode:** When `LITELLM_API_KEY` is configured in `.env`, the agent calls `azure/genailab-maas-gpt-4.1` (fallback `gemini-3-flash-preview`) via `https://genailab.tcs.in`, invokes MCP tools, and runs `grounding.check()`.
- **Rules Mode (`rules_mode`):** When no key is configured or the gateway is unreachable/ungrounded, the agent deterministically invokes the same engine tools and formats a verified response—**zero downtime, zero ungrounded numbers**.

---

## 8. Concise 5–7 Minute Judging Walkthrough

1. **0:00–1:00 — Problem & Option B Pitch:** Deliver the 60-second intro above.
2. **1:00–2:15 — `C001` Dashboard & Tariff:** Show `478.26 kWh`, `₹3,926.82`, `35%` Peak (`18:00–22:00` @ `₹10.20/kWh`), and 3 deterministic recommendations.
3. **2:15–3:30 — Live CSV Upload (`C098`):** Switch to `C098`, upload sample CSV, show validation summary, then switch back to `C001`.
4. **3:30–4:45 — What-If Simulation (`C001`):** Set `20%` Peak Shift + `1.0h` AC Trim → show `₹3,419.16` (`-₹507.66`, `-29.52 kg CO₂`) and dual-line chart.
5. **4:45–6:00 — Grounded AI Advisor & Fallback:** Ask *"Why is my bill high?"*, *"How much do I save in my simulation?"*, and *"Can you issue a refund on my bill?"* → highlight `grounded=true` and `rules_mode` resilience.
6. **6:00–6:45 — Admin & Audit + Limitations:** Open **Admin & Audit** tab (100 meters across 3 segments, 6 approved KB docs, pseudonymised audit log); briefly note enterprise roadmap (OAuth2/consent `FR-15`, live utility MCP servers, TimescaleDB).
