# EnergyWise AI — Option B PoC Low-Level Design (LLD)

| Attribute | Value |
| :--- | :--- |
| **Document ID** | `EW-LLD-OPTB-002` |
| **Version** | `0.2 (Aligned to Team Decisions D-1 to D-11 & Built Codebase)` |
| **Date** | 2026-11-27 |
| **Authors** | Sandeep / Dinesh (Lead Solution Architecture & Engineering) |
| **Scope** | **Option B PoC** — Deterministic Calculation Engines + Tool-Calling LLM Agent over MCP + Number-Level Grounding + PII Vault + Next.js 15 / FastAPI |

> [!NOTE]
> **Controlling Context:** This LLD v0.2 replaces `EnergyWise_AI_Option1_PoC_LLD_v0.1.md` and describes the **built Option B PoC application** governed by settled team decisions **D-1 through D-11**. Proposals from v0.1 that are not yet in the built codebase are captured in **Section 16 (Planned Additions)**.

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

## 3. Component Design & Built Repository Structure

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
- **Built Loader Columns:** `meter_id, ts, kwh`.
- **Recommended Aliases:** Support `timestamp` (alias for `ts`) and `consumption_kwh` (alias for `kwh`) to accept sample CSVs seamlessly.
- **Validation (Built Today):** Gaps imputed with hour-of-day mean; spikes > 5× hourly median replaced; both counted in the quality score. *(See Section 16 for planned preserve-and-flag enhancements.)*

---

## 5. Data Structures, Tool Contracts v2 & DTOs

### 5.1 Frozen Tool Contracts v2 (`energywise/contracts.py`)

| Tool | MCP Server | Input | Output (Key Fields) |
| :--- | :--- | :--- | :--- |
| `get_usage_summary` | `energywise-engines` | `cust_ref, period` | `total_kwh, est_cost_inr, peak_share_pct, baseload_kw, top_hours[], anomalies[], quality_score` |
| `get_tariff` | `energywise-engines` | `cust_ref` | `plan, peak_window, rates_inr_per_kwh` |
| `get_recommendation_candidates` | `energywise-engines` | `cust_ref` | `[{id, pattern, action, kwh_saving, inr_saving, confidence}]` |
| `simulate_scenario` | `energywise-engines` | `cust_ref, actions[]` (`shift_load`, `reduce_load`, `ac_hours`, `shift_kwh`) | `baseline/scenario/delta {kwh, cost_inr, peak_kwh, co2_kg}, assumptions[]` |
| `forecast` | `energywise-engines` | `cust_ref, actions?` | `next_month_kwh, next_month_cost_inr, method, confidence` |
| `search_kb` | `energywise-kb` | `query, doc_type?` | `[{text, source, doc_type, version, effective_from}]` |
| `fetch_intervals` | `smart-meter` | `meter_ref, days` | Readings from mock smart-meter API (**backend sync only; never called by LLM**) |

### 5.2 Simulation Request DTO
- Request payload: `{cust_ref, actions[]}` using `shift_load`, `reduce_load`, `ac_hours`, `shift_kwh` per `contracts.py` (no `ac_setpoint_c`).

---

## 6. SQLite Databases & Schema

1. **`data/pii_vault.db` (Isolated Vault — Never Opened by AI or MCP Servers):**
   - Stores `meter_id → cust_ref` mapping and synthetic personal fields (`name`, `address`, `phone`, `email`).
2. **`data/energywise.db` (Pseudonymised Domain Store, Keyed by `cust_ref`):**
   - `readings`: Pseudonymised hourly kWh interval series.
   - `profiles`: Customer segment, declared appliance estimates, quality score.
   - `feedback`: Customer 👍/👎 ratings on recommendations.
   - `audit`: Outgoing scanned LLM requests, MCP tool calls + results, grounding results.

---

## 7. FastAPI Endpoints (`api/main.py`)

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `GET` | `/health` | Service and gateway health check |
| `GET` | `/customers` | List pseudonymised customers (`C001`…) |
| `GET` | `/dashboard/{cust_ref}` | Usage summary, ToD bill, 24h profile, quality score (direct engine call) |
| `POST` | `/simulate` | Run what-if simulation `{cust_ref, actions[]}` + CO₂ delta (direct engine call) |
| `GET` | `/advice/{cust_ref}` | Agent-generated grounded recommendations (or rules mode fallback) |
| `POST` | `/chat` | Grounded conversational advisor turn |
| `POST` | `/feedback` | Store 👍/👎 feedback on advice |
| `POST` | `/upload` | Upload smart-meter CSV for ingestion & pseudonymisation |
| `GET` | `/admin/aggregates` | Demand-response aggregate view (`FR-12`) |
| `GET` | `/admin/documents` | Approved KB documents list (`data/kb/`) |
| `GET` | `/admin/audit` | Pseudonymised AI/MCP/grounding audit log |

---

## 8. Tariff, Time-of-Day Windows & Calculations (`D-6`, `D-8`, `D-9`)

- **Tariff (`TAR-ILL-001`):**
  - Off-Peak (`23:00–06:00`): `₹6.00/kWh`
  - Standard (`06:00–18:00`): `₹7.50/kWh`
  - **Peak (`18:00–22:00`):** `₹10.20/kWh`
  - Shoulder (`22:00–23:00`): `₹7.50/kWh`
  - ToU only; no slabs, no fixed charges.
- **Included Engines (`energywise/engines/tools.py`):**
  - **Analytics & Billing:** Deterministic kWh, cost, peak share %, baseload, anomalies.
  - **Simulator (`D-9`):** Appliance move (dropdown → `shift_kwh`), shift % of peak to night (`shift_load`), AC runtime trim (`ac_hours`), standby cut `0–30%` (`reduce_load`), and presets.
  - **CO₂ Estimate (`FR-18`) & Forecast (`FR-09`):** Computed deterministically in `tools.py` and returned in `simulate_scenario` and `forecast` tool outputs.

---

## 9. Agent Flow, MCP Orchestration & Grounding (`§3.1` & `§3.3`)

### 9.1 Option B Agent Flow (`energywise/agent/agent.py`)
```text
UI ─► FastAPI /advice/{cust_ref} or /chat ─► agent (energywise/agent/agent.py)
  1. Build messages: system rules + task (cust_ref only, never personal data)
  2. privacy.scan(messages) → redact user-typed PII; BLOCK if PII appears anywhere else
  3. LLM (LiteLLM gateway) returns tool_calls ─► agent calls tools over MCP ─► JSON results appended
  4. Repeat steps 2–3 (max 6 rounds) until the LLM returns final text
  5. grounding.check(reply, tool_outputs) ─► mismatch: regenerate once ─► still mismatch / LLM error / no key: RULES MODE
  6. Audit log: outgoing (scanned) request, every tool call + result, grounding result
```
*(Dashboard, simulator sliders, and bill breakdown bypass the LLM and call engines directly from FastAPI.)*

### 9.2 Number-Level Grounding Algorithm (`energywise/agent/grounding.py`)
- Extract every number from the reply (`18:00` counts as `18`; thousands separators allowed).
- A number is **grounded** if it equals any numeric value in that request's tool outputs after rounding to the displayed precision (`593.9` matches `₹594`); sign ignored (`-147` matches `saves ₹147`).
- Ignored: list markers, numbers typed by the user, small counting integers `0–5`.
- Numbers found **only in KB text** are reported separately (`from_documents`), not as engine-grounded.
- Output `{grounded, numbers, ungrounded, from_documents}` is surfaced in the UI and persisted in `audit`.

---

## 10. Privacy & Security Controls (`energywise/ingest/ingest.py`, `energywise/agent/privacy.py`)

- **Ingestion Pseudonymisation:** `meter_id → cust_ref` and personal fields (`name`, `address`, `phone`, `email`) are written **only** to `data/pii_vault.db`.
- **AI/MCP Isolation:** `energywise/agent/` and `energywise/mcp_servers/` never open `data/pii_vault.db` and operate strictly on `cust_ref`.
- **Outbound Privacy Scan:** `privacy.scan()` detects Indian mobile numbers, emails, `MTR-` meter IDs, and street-address patterns—redacting user-typed PII and blocking any other PII leak before calling the LLM gateway.

---

## 11. Configuration & Run Instructions

### 11.1 Environment Variables (`.env`)
- `LITELLM_BASE_URL=https://genailab.tcs.in`
- `LITELLM_API_KEY`
- `CHAT_MODEL=azure/genailab-maas-gpt-4.1`
- `FALLBACK_MODEL=gemini-3-flash-preview`
- `EMBED_MODEL=azure/genailab-maas-text-embedding-3-large`
- `USE_MCP=1` (1 = FastMCP stdio servers; 0 = direct registry fallback)
- `LLM_BUDGET_USD=25`

### 11.2 Run Steps
1. Generate synthetic data: `python -m energywise.data.generate`
2. Ingest & populate SQLite + PII vault: `python -m energywise.ingest.ingest`
3. Start FastAPI backend: `uvicorn api.main:app --port 8000`
4. Start Next.js UI (in `web/`):
   ```cmd
   set NODE_OPTIONS=--use-system-ca
   npm install
   npm run dev
   ```
5. Open `http://localhost:3000`.

---

## 12. Planned Additions (From v0.1 — Open Proposals for v0.2+)

The following items from v0.1 are **not** in the current built codebase and are proposed as incremental enhancements:

1. **Preserve Raw File & Raw Rows Untouched:** Store the original uploaded CSV file and raw rows verbatim alongside per-row validation issues.
2. **Standardised Issue Codes in Validation Summary:** Emit explicit codes (`DUPLICATE_TIMESTAMP`, `MISSING_INTERVAL`, `EXTREME_SPIKE`, `NEGATIVE_VALUE`, `OUT_OF_ORDER`) per dataset.
3. **Flag-Don't-Impute Policy (Proposal for Team Decision):** Current code imputes gaps with hour-of-day mean and replaces spikes `> 5×` hourly median. **Proposal:** Preserve gaps un-imputed (flagging them) and keep measured spikes visible on the chart while excluding only invalid/negative/duplicate rows—preventing silent modification of customer measurements.
4. **Faulty Sample Loader (`load-sample`):** Bundle a `sample_with_faults.csv` option for quick data-quality demoing.
5. **Non-Guaranteed Annual Savings Label:** Explicitly label `monthly × 12` annual projections as non-guaranteed estimates in the UI and advice cards.
6. **Automated Unit & API Tests (`FastAPI TestClient`):** Owned by Sandeep against the built `energywise/` + `api/` codebase (covering ingestion, isolation, billing, simulation, MCP tool calls, grounding, and rules-mode fallback).
