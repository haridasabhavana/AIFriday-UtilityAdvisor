# EnergyWise AI — Option B PoC Low-Level Design (LLD)
## Enhanced with EnergyWise Intelligence Loop (EIL)

| Attribute | Value |
| :--- | :--- |
| **Document ID** | `EW-LLD-OPTB-003` |
| **Version** | `0.3 (Option B Baseline + EnergyWise Intelligence Loop Enhancement — Pending Review Gate)` |
| **Date** | 2026-11-27 |
| **Authors** | Sandeep / Dinesh (Lead Solution Architecture & Engineering) |
| **Scope** | **Option B PoC** (Frozen Baseline `9e2c8df`) + **EnergyWise Intelligence Loop (EIL):** `DISCOVER → DECIDE → SIMULATE → ACT → VERIFY` |

> [!IMPORTANT]
> **Frozen Baseline & Review Gate Notice:** Sections `1`–`12` preserve the frozen Option B PoC baseline (`9e2c8df`, `EW-LLD-OPTB-002`). Sections `13`–`23` specify the **EnergyWise Intelligence Loop (EIL)** LLD enhancement. **No application code has been modified and no EIL implementation may begin until the Mandatory Review Gate (Section 23) is approved.**

---

## 1. Architecture Background (Deliverable D2: Options A, B, C)

The team evaluated three architectural options for **where the intelligence sits**:

| Option | Description | Decision |
| :--- | :--- | :--- |
| **Option A: LLM-centric advisor (RAG)** | LLM reads a data summary / JSON snapshot plus retrieved tips and computes advice, savings, and what-ifs itself. | **Rejected:** Risk of invented/mis-stated ₹ and kWh figures, data leakage into prompts, and no deterministic fallback. |
| **Option B: Calculation engine + tool-calling LLM agent** | Plain Python code computes **every number**. The LLM chooses which engine tools to call (function calling via MCP), receives tool outputs, and only **explains**. A grounding checker verifies every number in the reply; falls back to rules mode on failure. | **CHOSEN** (Score: 91/100). |
| **Option C: Rules + analytics only, no GenAI** | If-then rules and templated text only. | **Rejected as main design** (does not satisfy conversational AI advice); **retained inside Option B as the fallback "rules mode"**. |

---

## 2. Settled Team Decisions (D-1 to D-11)

| # | Topic | Settled Decision |
| :--- | :--- | :--- |
| **D-1** | **Architecture** | **Option B** (deterministic engines + tool-calling LLM agent + rules-mode fallback). |
| **D-2** | **AI ↔ Engine Boundary** | **Tool calling** using frozen **tool contracts v2** (`energywise/contracts.py`). |
| **D-3** | **Tool Protocol** | **MCP is required.** Engines and knowledge base are exposed as **MCP servers** (`FastMCP`, stdio); the agent is the **MCP client** (`USE_MCP=1/0` toggle). |
| **D-4** | **Grounding** | **Every number** in an AI reply must match a number in that request's tool outputs (after rounding); mismatch triggers 1 regeneration, else rules mode. |
| **D-5** | **Privacy** | **Pseudonymise at ingestion** (`meter_id` → `cust_ref` such as `C001`). Personal fields live only in a separate **PII vault** (`data/pii_vault.db`) unreachable by AI and MCP servers. Outgoing LLM requests pass `privacy.scan()`. |
| **D-6** | **Tariff (`TAR-ILL-001`)** | **One peak window: 18:00–22:00** (`₹10.20/kWh`). Off-peak `23:00–06:00` (`₹6.00/kWh`), Standard `06:00–18:00` (`₹7.50/kWh`), Shoulder `22:00–23:00` (`₹7.50/kWh`). ToU only, no slabs, no fixed charge. |
| **D-7** | **UI & API Stack** | **Next.js 15 + Tailwind** (`web/`, port `3000`) calling **FastAPI** (`api/`, port `8000`). Engines, agent, and MCP servers in **Python**. |
| **D-8** | **Scope** | **In scope:** CO₂ estimate (`FR-18`), forecast (`FR-09`), **admin / demand-response view** (`FR-12`), approved-documents list, and audit log. |
| **D-9** | **Simulator Controls** | Appliance move (dropdown), shift % of peak to night, **AC runtime trim**, standby cut (`0–30%`), and presets. **No AC set-point control** (no cited basis). |
| **D-10** | **Models & Gateway** | LiteLLM gateway `https://genailab.tcs.in` only. Chat: `azure/genailab-maas-gpt-4.1`; fallback: `gemini-3-flash-preview`; embeddings: `azure/genailab-maas-text-embedding-3-large`. App budget cap (team quota USD 25). |
| **D-11** | **Knowledge Base (RAG)** | Tejus's **illustrative set 1** (6 Markdown docs in `data/kb/`) with `version`, `status`, `approved_by`, `effective_from`. Only published + approved docs are retrievable. Docs explain only; they never supply ₹/kWh savings. |

---

## 3. Component Design & Built Repository Structure (Frozen Baseline `9e2c8df`)

```text
energywise/
  config.py              # Tariff (D-6 / TAR-ILL-001), appliance estimates, model IDs, paths
  contracts.py           # Tool contracts v2 (frozen; change only by team agreement)
  data/generate.py       # Synthetic generator: 100 customers, 90 days hourly, faults injected, synthetic CIS
  ingest/ingest.py       # Clean + quality score + pseudonymise (meter_id -> cust_ref); PII vault
  engines/tools.py       # Analytics, tariff, recommendations, simulator, forecast, CO2, search_kb, REGISTRY
  mcp_servers/
    engines_server.py    # FastMCP stdio server exposing engine tools
    kb_server.py         # FastMCP stdio server exposing search_kb
    smart_meter_server.py# FastMCP stdio server exposing fetch_intervals (backend sync only)
  agent/
    agent.py             # Tool-calling agent loop (max 6 rounds) + rules mode fallback
    mcp_client.py        # MCP client connecting to FastMCP servers
    llm.py               # LiteLLM gateway client + USD budget cap enforcement
    privacy.py           # Outbound privacy.scan() PII redaction / blocking
    grounding.py         # Number-level grounding validator
api/main.py              # FastAPI REST API (port 8000)
web/app/                 # Next.js 15 + Tailwind UI (port 3000): page.tsx, components.tsx, lib.ts
data/kb/                 # 6 approved illustrative Markdown documents (Tejus set 1)
data/pii_vault.db        # Isolated PII mapping & personal fields (unreachable by AI/MCP)
data/energywise.db       # Pseudonymised readings, profiles, feedback, audit log
```

---

## 4. Upload User Journey & CSV Contract

### 4.1 Upload Journey (Port 3000 → Port 8000)
1. User selects a synthetic customer by pseudonym (`C001`…) or uploads a CSV in the **Next.js UI** (`http://localhost:3000`).
2. UI posts the file to FastAPI `POST /upload` (`http://localhost:8000`).
3. `energywise/ingest/ingest.py` cleans/validates the CSV, computes the quality score, pseudonymises `meter_id → cust_ref` (storing any personal fields only in `data/pii_vault.db`), and writes readings to `data/energywise.db`.
4. Dashboard, bill breakdown, recommendations, and simulator refresh immediately via FastAPI direct engine calls (no LLM involved).

### 4.2 CSV Contract
- **Built Loader Columns:** `meter_id, ts, kwh` plus aliases `timestamp` and `consumption_kwh`.
- **Validation (Built Today):** Gaps imputed with hour-of-day mean; spikes > 5× hourly median replaced; raw rows preserved in `raw_readings` alongside `validation_issues`.

---

## 5. Data Structures, Tool Contracts v2 & DTOs

### 5.1 Frozen Tool Contracts v2 (`energywise/contracts.py`)

| Tool | MCP Server | Input | Output (Key Fields) |
| :--- | :--- | :--- | :--- |
| `get_usage_summary` | `energywise-engines` | `cust_ref, period` | `total_kwh, est_cost_inr, peak_share_pct, baseload_kw, top_hours[], anomalies[], quality_score` |
| `get_tariff` | `energywise-engines` | `cust_ref` | `plan, peak_window, rates_inr_per_kwh` |
| `get_recommendation_candidates` | `energywise-engines` | `cust_ref` | `[{id, pattern, action, kwh_shift, kwh_saving, inr_saving, confidence}]` |
| `simulate_scenario` | `energywise-engines` | `cust_ref, actions[]` (`shift_load`, `reduce_load`, `ac_hours`, `shift_kwh`) | `baseline/scenario/delta {kwh, cost_inr, peak_kwh, co2_kg}, assumptions[]` |
| `forecast` | `energywise-engines` | `cust_ref, actions?` | `next_month_kwh, next_month_cost_inr, method, confidence` |
| `search_kb` | `energywise-kb` | `query, doc_type?` | `[{text, source, doc_type, version, effective_from}]` |
| `fetch_intervals` | `smart-meter` | `meter_ref, days` | Readings from mock smart-meter API (**backend sync only; never called by LLM**) |

---

## 6. SQLite Databases & Schema (Frozen Baseline)

1. **`data/pii_vault.db`:** `pii_customers` (`cust_ref`, `meter_id`, `name`, `email`, `phone`, `address`). Never opened by AI or MCP servers.
2. **`data/energywise.db`:** `profiles`, `raw_readings`, `validation_issues`, `readings`, `feedback`, `audit`.

---

## 7. FastAPI Endpoints (Frozen Baseline)

`GET /health`, `GET /customers`, `GET /dashboard/{cust_ref}`, `POST /simulate`, `GET /advice/{cust_ref}`, `POST /chat`, `POST /feedback`, `POST /upload`, `GET /admin/aggregates`, `GET /admin/documents`, `GET /admin/audit`.

---

## 8. Tariff, Time-of-Day Windows & Calculations (`D-6`, `D-8`, `D-9`)

- **Tariff (`TAR-ILL-001`):** Off-Peak (`23–06`): `₹6.00/kWh`, Standard (`06–18`): `₹7.50/kWh`, **Peak (`18–22`): `₹10.20/kWh`**, Shoulder (`22–23`): `₹7.50/kWh`.
- **Reconciliation Rule:** `simulate_scenario` anchors `baseline` directly to `get_usage_summary` (`total_kwh`, `est_cost_inr`) and computes `scenario = baseline + delta` so Dashboard, Simulator, Forecast, and AI Chat match to `₹0.00` discrepancy.

---

## 9. Agent Flow, MCP Orchestration & Grounding

- **Agent Loop:** `messages` → `privacy.scan()` → LLM tool calls via FastMCP (`max 6 rounds`) → `grounding.check(reply, tool_outputs)` (1 regeneration retry on mismatch, else `rules_mode`) → `audit` log.
- **Number-Level Grounding:** Extracts numbers from reply (`HH:MM` → `HH`), matches against tool output numbers after rounding (ignoring sign, list markers, user-typed numbers, and `0–5`); KB-only numbers reported separately as `from_documents`.

---

## 10. Privacy & Security Controls

- Pseudonymisation at ingestion (`meter_id → cust_ref`); isolated `data/pii_vault.db`; outbound `privacy.scan()` redacting user PII and blocking PII in system/tool/assistant messages.

---

## 11. Configuration & Run Instructions

- `.env`: `LITELLM_BASE_URL`, `LITELLM_API_KEY`, `CHAT_MODEL`, `FALLBACK_MODEL`, `EMBED_MODEL`, `USE_MCP`, `LLM_BUDGET_USD`.
- Run: `python -m energywise.data.generate` → `python -m energywise.ingest.ingest` → `uvicorn api.main:app --port 8000` → `web/`: `npm run dev`.

---

## 12. Planned Additions (From v0.1 / v0.2)

1. Flag-don't-impute policy toggle (preserve gaps un-imputed and spikes visible).
2. `sample_with_faults` one-click loader in UI.
3. Non-guaranteed annual savings label (`monthly × 12`).

---

# PART II — EnergyWise Intelligence Loop (EIL) LLD Enhancement (v0.3)

---

## 13. Intelligence Loop Overview & Functional Requirements

The **EnergyWise Intelligence Loop (EIL)** evolves EnergyWise AI from a point-in-time advisor into a closed-loop five-stage optimisation cycle:

```text
[1. DISCOVER] ──► [2. DECIDE] ──► [3. SIMULATE] ──► [4. ACT] ──► [5. VERIFY]
     ▲                                                                 │
     └─────────────── Feed verified outcomes & new baseline ───────────┘
```

### 13.1 EIL Functional Requirements

| Req ID | Stage | Requirement Summary & Guardrails |
| :--- | :--- | :--- |
| **EIL-01** | **DISCOVER** *(Consumption Intelligence & Opportunity Discovery)* | Analyse historical readings; identify peak-period exposure (`18:00–22:00`), unusual changes/spikes, bill drivers, flexible load-shifting potential, and standby/excessive runtime evidence; explain supporting data. **Constraint:** Never claim appliance-level measurements where only aggregate meter readings exist; distinguish inferred/estimated appliance usage from measured meter usage. |
| **EIL-02** | **DECIDE** *(Intelligent Intervention Selection)* | Generate actionable interventions from discovered opportunities; rank by estimated financial benefit, kWh reduction, ease of adoption, confidence, and evidence; consider ToD tariff windows and customer patterns; exclude incompatible/unsupported actions; attach rationale, assumptions, evidence, and limitations. **Constraint:** Deterministic backend rules validate all actions and numerical impacts; LLM only explains/supports prioritisation. |
| **EIL-03** | **SIMULATE** *(What-If Simulation & Impact Assessment)* | Simulate one or more proposed interventions; calculate baseline vs. proposed kWh, bill (`₹`), and CO₂ (`kg`); show individual and combined impacts while **preventing double-counting** (e.g., capping combined peak-window reductions to available peak load); display **projected savings** separately from **realised savings**; maintain `₹0.00` reconciliation across Dashboard, Simulator, Recommendations, and AI Chat. |
| **EIL-04** | **ACT** *(Personalised Action Plan)* | Convert selected interventions into a prioritised action plan showing action, expected benefit, priority, and suggested execution window; explain customer relevance; allow consumers to mark actions `accepted`, `declined`, or `completed` (preserving action history and simulation assumptions). **Constraint:** Zero physical device control or automatic switching. |
| **EIL-05** | **VERIFY** *(Savings Verification)* | Compare post-intervention meter readings against a selected baseline period over comparable intervals and ToD windows; assess data completeness/quality; compute observed consumption and bill differences; compare **projected vs. observed** outcomes; attribute results to recorded interventions only where evidence permits, reporting confidence and limitations. **Constraint:** A simple difference between two bills must **never** be automatically labelled as causal savings; where seasonality, weather, occupancy, or tariff changes are unavailable, label as **observed change** (not proven causal savings). If subsequent meter data is insufficient, clearly indicate **Verification Pending**. |

### 13.2 EIL Traceability Matrix

| Req ID | Owning Backend Modules | EIL Logical Entities | API / MCP Tools | UI View |
| :--- | :--- | :--- | :--- | :--- |
| **EIL-01** | `analytics.py`, `discovery.py` (new) | `EnergyOpportunity`, `InterventionEvidence` | `discover_opportunities` | Opportunity Overview |
| **EIL-02** | `recommendations.py`, `interventions.py` (new) | `Intervention`, `InterventionEvidence` | `rank_interventions` | Recommended Actions |
| **EIL-03** | `tools.py` (`simulate_scenario`) | `SimulationScenario` | `simulate_scenario` | What-if Comparison |
| **EIL-04** | `action_plan.py` (new), `db` | `ActionPlan`, `ActionPlanItem`, `CustomerActionStatus` | `manage_action_plan`, `update_action_status` | My Energy Action Plan |
| **EIL-05** | `verification.py` (new), `analytics.py` | `SavingsBaseline`, `VerificationPeriod`, `SavingsVerificationResult` | `create_baseline`, `verify_savings` | Savings Tracker |
| **All** | `agent.py`, `grounding.py`, `privacy.py` | All EIL entities (read-only context) | `get_intelligence_loop_summary` | AI Explanation |

---

## 14. EIL Architecture & Component Responsibilities

### 14.1 Reuse vs. Enhancement vs. New Modules

No microservices or external infrastructure are added; all EIL logic resides cleanly inside the existing `energywise/` Python package and `data/energywise.db` SQLite database.

| Capability | Existing Module(s) Reused | Enhancement / New Logical Module | Responsibility |
| :--- | :--- | :--- | :--- |
| **Consumption Analytics & Anomalies** | `energywise/engines/tools.py` (`get_usage_summary`) | **Reuse + Minor Enhance** | Provide measured kWh, peak share, baseload, top hours, spike flags, and period-sliced summaries for arbitrary date ranges (`start_ts`, `end_ts`). |
| **Opportunity Discovery (`DISCOVER`)** | `tools.py` | **New:** `energywise/engines/discovery.py` | Deterministic rules scanning usage summaries, ToD exposure, baseload, and spikes to emit `EnergyOpportunity` records with `InterventionEvidence`. |
| **Intervention Generation & Ranking (`DECIDE`)** | `tools.py` (`get_recommendation_candidates`) | **New:** `energywise/engines/interventions.py` | Converts opportunities into `Intervention` candidates, filters incompatible actions, scores/ranks deterministically (INR saving, kWh, ease, confidence). |
| **Deterministic Impact & Simulation (`SIMULATE`)** | `tools.py` (`simulate_scenario`, `forecast`) | **Enhance `tools.py`** | Support multi-intervention combined simulation with **anti-double-counting guards** (cap sequential peak reductions to remaining peak load). |
| **Action-Plan Management (`ACT`)** | `energywise.db` | **New:** `energywise/engines/action_plan.py` | Creates/updates `ActionPlan` and `ActionPlanItem`, snapshots simulation assumptions, and records `CustomerActionStatus` (`accepted`/`declined`/`completed`). |
| **Savings Verification (`VERIFY`)** | `tools.py`, `ingest.py` | **New:** `energywise/engines/verification.py` | Locks `SavingsBaseline`, matches comparable `VerificationPeriod` intervals/ToD windows, checks completeness, computes observed vs. projected deltas, and enforces causal-claim guardrails. |
| **AI Explanation & Grounding** | `agent.py`, `grounding.py`, `privacy.py` | **Enhance `agent.py` & `mcp_servers/engines_server.py`** | Expose EIL read/summary tools to the agent; enforce strict EIL grounding rules (never confuse projected vs. observed vs. verified savings). |
| **Persistence** | `data/energywise.db` | **Extend SQLite schema** | Add EIL tables (`opportunities`, `action_plans`, `action_plan_items`, `savings_baselines`, `savings_verifications`) keyed strictly by `cust_ref`. |

### 14.2 Updated Component Architecture Diagram

```mermaid
flowchart TB
    UI["Next.js 15 UI (web/)\n6 EIL Views + Customer & Admin"] <-->|"HTTP/JSON"| API["FastAPI (api/main.py)\nEIL + Core Endpoints"]

    API -->|"Direct Deterministic Calls"| EIL_Eng
    API -->|"Advice & Chat"| Agent["Option B Agent (agent.py)\nprivacy.scan + grounding.check + rules_mode"]
    Agent <-->|"FastMCP stdio"| MCP["engines_server.py & kb_server.py"]
    MCP --> EIL_Eng

    subgraph EIL_Eng["energywise/engines/ (Deterministic Python)"]
        Core["tools.py (Summary, Tariff, Sim, Forecast, CO2)"]
        Disc["discovery.py (DISCOVER)"]
        Intv["interventions.py (DECIDE)"]
        Plan["action_plan.py (ACT)"]
        Ver["verification.py (VERIFY)"]
        Disc --> Core
        Intv --> Core
        Plan --> Intv
        Ver --> Core
    end

    EIL_Eng <-->|"cust_ref scoped"| DB["data/energywise.db\n(Readings, Plans, Baselines, Verifications, Audit)"]
    Ingest["ingest.py"] -->|"Pseudonymised readings"| DB
    Ingest -->|"PII isolated"| Vault["data/pii_vault.db"]
```

### 14.3 Complete 5-Stage Intelligence Loop Sequence Diagram

```mermaid
sequenceDiagram
    actor Cust as Customer (cust_ref)
    participant UI as Next.js UI
    participant API as FastAPI
    participant Eng as EIL Deterministic Engines
    participant Agent as Option B Agent + MCP
    participant DB as energywise.db

    Cust->>UI: 1. Open Intelligence Loop
    UI->>API: GET /eil/{cust_ref}/summary
    API->>Eng: DISCOVER opportunities & DECIDE ranked interventions
    Eng->>DB: Read measured readings & quality_score
    Eng-->>API: EnergyOpportunity[] + ranked Intervention[]
    API-->>UI: Render Opportunity Overview & Recommended Actions

    Cust->>UI: 2. Select interventions & SIMULATE
    UI->>API: POST /simulate (combined actions, no double-counting)
    API->>Eng: simulate_scenario (check bounds & peak capacity)
    Eng-->>API: Baseline vs. Projected Scenario + CO2
    API-->>UI: Render What-if Comparison (labelled Projected)

    Cust->>UI: 3. ACT — Save to My Energy Action Plan
    UI->>API: POST /eil/{cust_ref}/action-plan + status updates
    API->>Eng: Snapshot assumptions & persist ActionPlan
    Eng->>DB: Save ActionPlan, ActionPlanItem, CustomerActionStatus
    API-->>UI: Render My Energy Action Plan

    Cust->>UI: 4. VERIFY — Compare post-intervention readings
    UI->>API: POST /eil/{cust_ref}/verify
    API->>Eng: Compare VerificationPeriod vs. SavingsBaseline
    Eng->>DB: Read baseline & subsequent readings + quality flags
    alt Insufficient subsequent readings (< min_days or low completeness)
        Eng-->>API: status = "verification_pending"
    else Comparable period available
        Eng-->>API: status = "observed_change" (projected vs. observed + limitations)
    end
    API-->>UI: Render Savings Tracker (Projected vs. Observed)

    Cust->>UI: 5. Ask AI Advisor about loop results
    UI->>API: POST /chat
    API->>Agent: privacy.scan -> MCP EIL summary -> grounding.check -> audit
    Agent-->>API: Grounded explanation (or rules_mode)
    API-->>UI: Display AI Explanation with citations
```

---

## 15. EIL Logical Data Model & Contracts

### 15.1 Logical Entities Specification

All EIL entities are keyed by `cust_ref` (`Privacy: Pseudonymised`), never store direct PII, and write audit records for state changes.

| Entity | Primary ID | Key Attributes & Association | Lifecycle / Status | Source Evidence & Versioning |
| :--- | :--- | :--- | :--- | :--- |
| **`EnergyOpportunity`** | `opp_id` | `cust_ref`, `dataset_ref`, `category` (`peak_exposure`, `ac_runtime`, `standby`, `anomaly`), `severity`, `detected_at`, `evidence_ids[]` | `active` → `addressed` / `dismissed` | Linked to `InterventionEvidence`; `tariff_version = TAR-ILL-001`. |
| **`Intervention`** | `int_id` | `cust_ref`, `opp_id`, `action_type` (`shift_load`, `shift_kwh`, `ac_hours`, `reduce_load`), `rank`, `est_kwh_saving`, `est_inr_saving`, `est_co2_kg`, `ease_score`, `confidence`, `assumptions[]`, `limitations` | `proposed` → `selected` / `rejected` | Backed by `InterventionEvidence`; deterministic rule version `v1`. |
| **`InterventionEvidence`** | `ev_id` | `cust_ref`, `metric_name`, `measured_value`, `period_start`, `period_end`, `quality_score`, `is_inferred` (bool) | Immutable snapshot | Traceable to `readings` window; distinguishes measured vs. inferred. |
| **`SimulationScenario`** | `sim_id` | `cust_ref`, `actions[]`, `baseline_snapshot`, `projected_snapshot`, `delta`, `anti_double_count_notes[]`, `created_at` | `draft` → `locked_in_plan` | Snapshot of `TAR-ILL-001` & `CO2_KG_PER_KWH`. |
| **`ActionPlan`** | `plan_id` | `cust_ref`, `sim_id`, `title`, `created_at`, `updated_at`, `total_projected_inr`, `total_projected_kwh` | `active` → `completed` / `archived` | Preserves simulation assumptions at plan creation. |
| **`ActionPlanItem`** | `item_id` | `plan_id`, `int_id`, `priority`, `execution_window` (e.g. `18:00-22:00 → 23:00-06:00`), `relevance_reason`, `expected_inr_saving` | `pending` / `accepted` / `declined` / `completed` | Inherits `InterventionEvidence` & assumptions. |
| **`CustomerActionStatus`** | `status_id` | `item_id`, `cust_ref`, `status` (`accepted`/`declined`/`completed`), `recorded_at`, `note` | Append-only history | Audited status transitions for attribution. |
| **`SavingsBaseline`** | `baseline_id` | `cust_ref`, `plan_id`, `period_start`, `period_end`, `total_kwh`, `est_cost_inr`, `peak_kwh`, `quality_score`, `tariff_version` | `locked` | Immutable reference prior to action adoption. |
| **`VerificationPeriod`** | `ver_period_id` | `cust_ref`, `baseline_id`, `period_start`, `period_end`, `interval_count`, `completeness_pct`, `quality_score` | `pending_data` → `ready` | Raw readings preserved; missing intervals flagged (not imputed). |
| **`SavingsVerificationResult`** | `ver_id` | `cust_ref`, `baseline_id`, `ver_period_id`, `projected_kwh_delta`, `observed_kwh_delta`, `projected_inr_delta`, `observed_inr_delta`, `outcome_label` (`verification_pending` / `observed_change` / `inconclusive`), `confidence`, `confounding_factors[]`, `limitations` | `computed` (immutable per period) | Never claims causal savings without seasonality/weather/occupancy evidence. |

### 15.2 Example Request / Response Contracts

**Action Plan Creation (`POST /eil/{cust_ref}/action-plan`):**
```json
{
  "cust_ref": "C001",
  "intervention_ids": ["INT-SHIFT-PEAK", "INT-AC-TRIM"],
  "actions": [{"type": "shift_load", "pct": 20}, {"type": "ac_hours", "hours": 1.0}]
}
```
Response:
```json
{
  "plan_id": "PLN-C001-01",
  "status": "active",
  "total_projected_inr_saving": 507.66,
  "projection_label": "Projected (not yet verified)",
  "items": [
    {"item_id": "ITM-01", "priority": 1, "status": "pending", "execution_window": "Shift 18:00-22:00 -> 23:00-06:00"}
  ]
}
```

**Savings Verification (`POST /eil/{cust_ref}/verify`):**
```json
{
  "cust_ref": "C001",
  "baseline_id": "BAS-C001-01",
  "post_start": "2026-10-01T00:00:00+05:30",
  "post_end": "2026-10-30T23:00:00+05:30"
}
```
Response (when weather/occupancy context is unavailable):
```json
{
  "ver_id": "VER-C001-01",
  "outcome_label": "observed_change",
  "projected_inr_delta": -507.66,
  "observed_inr_delta": -412.40,
  "completeness_pct": 98.6,
  "confidence": "Medium",
  "limitations": "Weather, occupancy, and seasonal factors are not available; result is an observed change rather than proven causal savings."
}
```

---

## 16. EIL API & MCP Tool Design

### 16.1 Proposed FastAPI Endpoints & Internal MCP Tools

All calculations execute in deterministic Python engines (`energywise/engines/`). FastAPI serves the UI directly; internal MCP tools (`engines_server.py`) expose read-only summary/discovery/verification tools to the Option B agent. No external MCP integrations are introduced.

| Operation | FastAPI Endpoint | Internal MCP Tool | Validation & No-Data / Error Behaviour | Isolation & Audit |
| :--- | :--- | :--- | :--- | :--- |
| **Discover Opportunities** | `GET /eil/{cust_ref}/opportunities` | `discover_opportunities(cust_ref, period)` | Requires ≥ 7 days valid readings; else returns `insufficient_data`. | Scoped to `cust_ref`; logged if invoked by agent. |
| **Rank Interventions** | `GET /eil/{cust_ref}/interventions` | `rank_interventions(cust_ref)` | Filters incompatible actions; returns empty list with reason if no data. | Scoped to `cust_ref`. |
| **Simulate Combined** | `POST /simulate` *(existing)* | `simulate_scenario` *(existing)* | Validates bounds (`pct`, `hours`) and caps combined peak shifts to prevent double-counting. | Scoped to `cust_ref`. |
| **Create/Update Action Plan** | `POST /eil/{cust_ref}/action-plan` | *(UI/API only — LLM cannot mutate plans)* | Validates `int_id` belongs to `cust_ref`; snapshots simulation assumptions. | Scoped to `cust_ref`; audit row written. |
| **Record Action Status** | `PATCH /eil/{cust_ref}/action-plan/{item_id}` | *(UI/API only)* | Enum check: `accepted` / `declined` / `completed`; returns `404` on cross-customer access. | Scoped to `cust_ref`; append-only `CustomerActionStatus`. |
| **Establish Baseline** | `POST /eil/{cust_ref}/baseline` | *(UI/API only)* | Requires ≥ 14 days & `quality_score >= 70`; else `422` with clear message. | Scoped to `cust_ref`. |
| **Verify Savings** | `POST /eil/{cust_ref}/verify` | `get_savings_verification(cust_ref, plan_id)` *(read-only)* | Returns `verification_pending` if post-period < 7 days or completeness < 80%; never imputes missing data. | Scoped to `cust_ref`; audit logged. |
| **EIL Summary** | `GET /eil/{cust_ref}/summary` | `get_intelligence_loop_summary(cust_ref)` | Aggregates all 5 stages cleanly; omits missing stages gracefully. | Scoped to `cust_ref`. |

---

## 17. EIL AI Agent & Grounding Design

- **Agent Capabilities:** Explains discovered opportunities, intervention rankings, intervention comparisons, simulation deltas, action-plan progress, projected vs. observed savings, and why a verification result is `verification_pending` or `inconclusive`.
- **Agent Read-Only Tool Allowlist:** `get_usage_summary`, `get_tariff`, `discover_opportunities`, `rank_interventions`, `simulate_scenario`, `forecast`, `get_intelligence_loop_summary`, `get_savings_verification`, `search_kb`. *(Write operations—creating plans, updating action status, locking baselines—remain user-triggered API actions only, never autonomous LLM mutations.)*
- **Strict EIL Grounding & Guardrails:**
  - `grounding.check()` continues verifying every number against tool outputs (with 1 retry, else `rules_mode`).
  - System rules forbid: inventing measured kWh, presenting `projected` savings as `achieved`/`verified`, claiming causal proof without weather/occupancy evidence, presenting low-completeness data as conclusive, or leaking PII (`privacy.scan()`).

---

## 18. EIL User Experience & Presentation Design

### 18.1 Six Logical Views in Next.js (`web/app/`)

```text
+-----------------------------------------------------------------------------+
| EnergyWise AI [C001 v]   [Dashboard] [Intelligence Loop] [Admin & Audit]    |
+-----------------------------------------------------------------------------+
| EIL Stage Bar: [1.Discover] -> [2.Decide] -> [3.Simulate] -> [4.Act] -> [5.Verify] |
+------------------------------------+----------------------------------------+
| LEFT: Stage Workspace              | RIGHT: AI Explanation (Grounded Chat)  |
| - 1. Opportunity Overview          | - "Why is Peak 35% my top driver?"     |
| - 2. Recommended Actions (Ranked)  | - "Compare Shifting vs. AC Trim"       |
| - 3. What-if Comparison (Projected)| - "Why is my savings verification      |
| - 4. My Energy Action Plan         |    labelled Observed Change?"          |
| - 5. Savings Tracker (Projected    | [Rules Mode / LLM Grounded Badge]      |
|      vs. Pending vs. Observed)     |                                        |
+------------------------------------+----------------------------------------+
```

### 18.2 Mandatory Visual Badge Distinction
Every metric card and table row in the UI must display an explicit provenance pill:
- `MEASURED` (Slate/Blue): Smart-meter interval readings (`478.26 kWh`, `₹3,926.82`).
- `ESTIMATED` (Amber): Inferred/declared appliance loads (`Washing Machine est. 36 kWh/mo`).
- `PROJECTED (SIMULATED)` (Teal): What-if savings (`-₹507.66/mo projected`).
- `OBSERVED CHANGE` (Indigo): Post-intervention meter comparison where confounders are unmeasured.
- `VERIFICATION PENDING` (Gray): Insufficient post-intervention readings.

---

## 19. EIL Non-Functional Requirements

| Category | Requirement & Acceptance Criterion |
| :--- | :--- |
| **Accuracy & Reproducibility** | Identical inputs produce identical opportunity scores, rankings, bills, and verification deltas (`₹0.00` discrepancy across views). |
| **Incomplete-Period Handling** | Verification periods with `< 80%` interval completeness or `< 7` days are flagged `verification_pending` / `inconclusive`; raw readings are never silently altered. |
| **Performance** | `DISCOVER` + `DECIDE` + `VERIFY` deterministic endpoints respond in `< 300 ms` for 90-day hourly customer datasets. |
| **Privacy & Isolation** | All EIL tables and MCP tools use `cust_ref` only; cross-customer queries return `404`; `pii_vault.db` remains untouched. |
| **Auditability** | Every action-plan change, baseline lock, verification run, and AI explanation is logged with timestamps and grounding status. |
| **Reliability & Grounding** | `rules_mode` supports all 5 EIL stages if the LLM gateway is offline; `grounding.check()` blocks ungrounded figures. |

---

## 20. EIL Acceptance Test Scenarios (13 Scenarios)

| # | Scenario | Expected Outcome | Req Trace |
| :-: | :--- | :--- | :---: |
| **1** | Detect peak-period opportunity (`C001`, 35% peak) | Emits `EnergyOpportunity` (`peak_exposure`) with `35.0%` & `167.22 kWh` evidence. | `EIL-01` |
| **2** | Generate tariff-aware intervention | Recommends shifting load from `18:00–22:00` (`₹10.20`) to `23:00–06:00` (`₹6.00`). | `EIL-02` |
| **3** | Compare two alternative interventions | Ranks Peak Shift vs. AC Trim with individual ₹/kWh/CO₂, ease, and confidence. | `EIL-02` |
| **4** | Combined savings without double-counting | Combined `shift_load` + `ac_hours` caps peak reduction to available peak load; `delta <= peak_kwh`. | `EIL-03` |
| **5** | Create an action plan | Persists `ActionPlan` + `ActionPlanItem[]` with locked simulation assumptions and `Projected` label. | `EIL-04` |
| **6** | Record `accepted`, `declined`, `completed` | `CustomerActionStatus` appends each transition; declined items excluded from attribution. | `EIL-04` |
| **7** | Compare subsequent readings with baseline | Computes `observed_kwh_delta` and `observed_inr_delta` over matching ToD windows. | `EIL-05` |
| **8** | Incomplete or poor-quality readings | Period with 40% missing intervals returns `inconclusive` / `low_completeness` warning; no imputation. | `EIL-05` |
| **9** | Distinguish projected vs. observed savings | UI & API return separate `projected_inr_delta` and `observed_inr_delta` fields. | `EIL-03`, `EIL-05` |
| **10** | Reject unsupported causal savings claims | Without weather/occupancy data, `outcome_label = "observed_change"` (never `"verified_causal"`). | `EIL-05` |
| **11** | Verify numerical grounding in AI explanations | `grounding.check()` passes `grounded=True` on EIL chat replies; ungrounded numbers trigger retry/fallback. | `EIL-01`–`EIL-05` |
| **12** | Customer isolation & PII protection | `C002` cannot read `C001`'s action plan or verification; `privacy.scan()` blocks PII. | `D-5` |
| **13** | Missing post-intervention data | `POST /eil/C001/verify` with 0 post-period rows returns `outcome_label = "verification_pending"`. | `EIL-05` |

---

## 21. Phased Implementation Plan & Effort Estimates

### 21.1 Feature Classification Matrix

| Phase | Features Included | Est. Effort |
| :--- | :--- | :---: |
| **Existing & Reusable (Frozen `9e2c8df`)** | `get_usage_summary`, `get_tariff`, `simulate_scenario`, `forecast`, `search_kb`, `privacy.scan()`, `grounding.check()`, `rules_mode`, SQLite + PII vault, Next.js UI. | `0 days` *(Built)* |
| **Phase 1 — Intelligence & Action** *(Smallest Convincing PoC Slice)* | `discovery.py` (`EIL-01`), `interventions.py` (`EIL-02`), anti-double-counting guard in `tools.py` (`EIL-03`), `action_plan.py` (`EIL-04`), EIL UI views 1–4 + AI explanation hooks. | `~2–3 dev days` |
| **Phase 2 — Savings Verification** | `verification.py` (`EIL-05`), `SavingsBaseline` + `VerificationPeriod` + `SavingsVerificationResult` tables, synthetic post-intervention dataset split (Days 1–60 baseline vs. Days 61–90 post), Savings Tracker UI view 5. | `~2 dev days` |
| **Phase 3 — Advanced Intelligence** *(Post-PoC)* | Weather/temperature normalization, occupancy/calendar context, ML-assisted anomaly diagnosis, utility-wide DR programme optimization. | `Future Roadmap` |

*(Smallest convincing PoC demonstration: split `C001`'s existing 90-day synthetic dataset into Days 1–60 baseline and Days 61–90 simulated/perturbed post-intervention readings so all 5 EIL stages can be demonstrated end-to-end without external feeds.)*

---

## 22. Open Decisions, Assumptions, Risks & Dependencies

| ID | Type | Description | Owner / Decision Needed |
| :--- | :---: | :--- | :--- |
| **EIL-OD-01** | Open Decision | Confirm whether `energywise/contracts.py` (frozen in D-2) may be extended with `discover_opportunities`, `rank_interventions`, `get_intelligence_loop_summary`, and `get_savings_verification`. | Team Agreement (Dinesh / Sandeep) |
| **EIL-OD-02** | Open Decision | Confirm minimum completeness threshold (proposed `80%`) and minimum days (proposed `7 days`) for `SavingsVerificationResult` vs. `verification_pending`. | Domain SME / QA Lead |
| **EIL-A-01** | Assumption | Synthetic post-intervention period (Days 61–90) is acceptable to demonstrate Phase 2 `VERIFY` in PoC. | Product / Jury Lead |
| **EIL-R-01** | Risk | Users misinterpret `observed_change` as guaranteed causal savings. **Mitigation:** Mandatory UI `OBSERVED CHANGE` badge and explicit confounder disclaimer. | UX / AI Lead |

---

## 23. Backward-Compatibility Assessment & Mandatory Review Gate

- **Backward Compatibility:** 100% backward-compatible with frozen Option B baseline (`9e2c8df`). Existing endpoints (`/health`, `/customers`, `/dashboard/{cust_ref}`, `/simulate`, `/advice/{cust_ref}`, `/chat`, `/feedback`, `/upload`, `/admin/*`) and existing `contracts.py` tools remain unchanged in signature and behaviour; EIL adds additive tables, additive `/eil/*` routes, and additive MCP tools.
- **Mandatory Review Gate:** Implementation of Phases 1–2 is **held** pending explicit stakeholder/team approval of:
  1. `EIL-OD-01` (extending frozen `contracts.py` v2 with EIL read-only tools).
  2. `EIL-OD-02` (verification completeness/duration thresholds).
  3. Confirmation to branch off frozen judging baseline `9e2c8df` before writing any Phase 1 code.
