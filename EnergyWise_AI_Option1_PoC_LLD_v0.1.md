# EnergyWise AI — Option 1 PoC Low-Level Design (LLD)

| Attribute | Value |
| :--- | :--- |
| **Document ID** | `EW-LLD-OPT1-001` |
| **Version** | `0.1 (Fast-Track Three-Hour Demo Baseline)` |
| **Date** | 2026-11-27 |
| **Controlling HLD** | [EnergyWise_AI_Option1_PoC_HLD_v1.2.md](file:///c:/Users/GenAIBLRANCUSR31/Documents/EnergyWise%20Ai/EnergyWise_AI_Option1_PoC_HLD_v1.2.md) (v1.3) |
| **Scope** | Option 1 PoC Customer Journey — CSV Upload, Validation, Analytics, Billing, Recommendations, What-If Simulation, Grounded AI Advisor & Deterministic Fallback |

> [!NOTE]
> **Provisional PoC Assumptions:** All technology choices below (FastAPI, Pydantic, SQLite, local CSV storage, static synthetic KB, React + lightweight SVG charting, selector-based appliance shifting, no login, no CO₂, no forecasting, no admin analytics, no MCP) are **provisional PoC assumptions** adopted for the 3-hour demo, not formally approved enterprise decisions.

---

## 1. Component and Module Design

The single-deployable PoC application consists of a **React SPA** (`frontend/`, built to `frontend/dist/`) served by a **FastAPI** backend (`backend/`) hosting logically separated Python modules:

```
EnergyWise Ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # M2: FastAPI app, routes, dataset isolation, static SPA serving
│   │   ├── config.py            # Configurable thresholds, tariff schedule, LLM gateway settings
│   │   ├── models.py            # Pydantic DTOs for API requests/responses
│   │   ├── db.py                # M12: SQLite schema & dataset-scoped repository
│   │   ├── ingestion.py         # M3/M4: CSV parser, raw file/row preservation, preserve-and-flag validator
│   │   ├── analytics.py         # M5: Measured kWh, 24h profile, ToD split, spike/overnight flags
│   │   ├── billing.py           # M6: Authoritative deterministic ToD tariff & bill engine
│   │   ├── recommendations.py   # M7: Deterministic opportunity rules, confidence/limitations, static KB
│   │   ├── simulation.py        # M9: Deterministic what-if engine (appliance shift, AC, standby)
│   │   └── ai_advisor.py        # M8/M10: Grounded LLM adapter + tool/context + deterministic fallback
│   └── tests/
│       └── test_core.py         # Unit & API tests (unittest + FastAPI TestClient)
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # M1: Customer journey UI (Upload, Dashboard, Bill, Recs, Simulator, Chat)
│   │   └── components/          # LoadChart (inline SVG), QualityReport, SimulatorControls, ChatPanel
│   └── dist/                    # Built static SPA served by FastAPI
├── data/
│   ├── sample_smart_meter.csv   # Clean 30-day (720-hour) synthetic dataset
│   └── sample_with_faults.csv   # Synthetic dataset with faults to demonstrate preserve-and-flag
└── .env.example                 # Gateway URL, key placeholder, model IDs, validation thresholds
```

### Module Mapping to HLD
- **M1 (UI / Presentation):** `frontend/src/` (React + Tailwind/CSS + responsive SVG 24h chart).
- **M2 (Backend / Orchestration):** `backend/app/main.py` (REST/JSON endpoints + dataset isolation).
- **M3 / M4 (Ingestion & Validation):** `backend/app/ingestion.py`.
- **M5 (Consumption Analytics):** `backend/app/analytics.py`.
- **M6 (Tariff & Bill Calculation):** `backend/app/billing.py`.
- **M7 (Recommendation Engine):** `backend/app/recommendations.py`.
- **M8 / M10 (AI Adapter & Conversational Advisor):** `backend/app/ai_advisor.py`.
- **M9 (What-if Simulation):** `backend/app/simulation.py`.
- **M12 (Data Persistence):** `backend/app/db.py` + `uploads/` local file store.
- **M11 (Utility/Admin Analytics):** Excluded in 3-hour demo per Part A assumptions.

---

## 2. CSV Upload UI and User Journey

1. Customer opens EnergyWise AI (`http://localhost:8000`) and selects or creates a synthetic customer profile (e.g., `CUST_DEMO_01` default).
2. Customer clicks **Upload Smart-Meter CSV** (or loads the bundled sample CSV path) and submits the `.csv` file.
3. UI calls `POST /api/datasets/upload?customer_id=...` with `multipart/form-data`.
4. UI displays upload status, `dataset_id`, total raw rows, valid rows, flagged issues count, and an expandable **Validation & Remediation Summary** table.
5. UI automatically fetches dashboard metrics, bill breakdown, recommendations, and enables the what-if simulator and AI advisor chat for that `dataset_id`.

---

## 3. CSV Parsing and Validation

### Agreed Synthetic CSV Contract
```csv
meter_id,timestamp,consumption_kwh
MTR001,2026-11-01T00:00:00+05:30,0.42
```

- **Required Columns:** `meter_id` (non-empty string, synthetic), `timestamp` (ISO 8601 with timezone offset), `consumption_kwh` (numeric float).
- **Ownership:** `customer_id` and `dataset_id` are assigned/bound by the backend (`M2`), never trusted from CSV columns.

### Deterministic Validation Rules (Configurable in `config.py`)
1. **Missing Required Columns:** Reject file (`HTTP 400`) if any of `meter_id`, `timestamp`, `consumption_kwh` is absent or file is empty.
2. **Invalid Timestamps / Non-Numeric / Negative Values:** Flag row (`INVALID_TIMESTAMP`, `NON_NUMERIC`, `NEGATIVE_VALUE`); exclude from normalised analytics while preserving raw row.
3. **Duplicate `(meter_id, timestamp)`:** Flag duplicate occurrences (`DUPLICATE_TIMESTAMP`); retain first valid occurrence in normalised series and exclude duplicates from analytics.
4. **Out-of-Order Timestamps:** Flag (`OUT_OF_ORDER`) when timestamp decreases relative to previous valid row; sort chronologically in the separate normalised view while keeping raw row order untouched.
5. **Missing Intervals:** Detect gaps > 60 minutes between consecutive valid sorted timestamps; flag gap (`MISSING_INTERVAL`) in validation report; **do not impute** readings.
6. **Extreme Spikes:** Flag readings exceeding `SPIKE_THRESHOLD_KWH` (default configurable `5.0 kWh/hr`) as `EXTREME_SPIKE`; **retain** valid measured readings in analytics and mark them on the chart.
7. **Raw Preservation:** Save original CSV bytes to `uploads/{dataset_id}.csv` and every raw row to `raw_readings` untouched.
8. **Separate Storage:** Write flagged issues to `validation_issues` and clean sorted series to `normalised_readings`.

---

## 4. Data Structures and DTOs (`models.py`)

Key Pydantic models:
- `UploadResponse`: `dataset_id`, `customer_id`, `filename`, `raw_row_count`, `valid_row_count`, `flagged_count`, `missing_gap_count`, `quality_summary`, `issues: list[ValidationIssueDTO]`.
- `DashboardResponse`: `dataset_id`, `customer_id`, `total_kwh`, `avg_daily_kwh`, `peak_kwh`, `peak_share_pct`, `estimated_bill`, `currency`, `hourly_profile: list[HourlyPointDTO]`, `window_breakdown: list[WindowBreakdownDTO]`, `spike_count`, `data_quality_note`.
- `RecommendationDTO`: `rec_id`, `title`, `reason`, `evidence`, `estimated_monthly_kwh_saved`, `estimated_monthly_bill_saved`, `projected_annual_savings_note`, `assumptions`, `confidence`, `limitations`, `kb_citation`, `explanation`, `feedback`.
- `SimulationRequest`: `dataset_id`, `appliance_shifts: dict[str, str]` (appliance_id → target window), `ac_setpoint_c: int`, `peak_ac_trim_hours: float`, `standby_reduction_pct: int`.
- `SimulationResponse`: `baseline_kwh`, `simulated_kwh`, `baseline_bill`, `simulated_bill`, `monthly_savings`, `projected_annual_savings`, `projection_disclaimer`, `baseline_peak_pct`, `simulated_peak_pct`, `hourly_comparison`, `appliance_estimate_disclaimer`.
- `ChatRequest` / `ChatResponse`: `dataset_id`, `question`, `answer`, `citations: list[str]`, `used_fallback: bool`, `grounding_note`.

---

## 5. SQLite Schema and Repository Interfaces (`db.py`)

Tables (all dataset-scoped via `dataset_id` + `customer_id`):
- `datasets` (`dataset_id PK`, `customer_id`, `filename`, `raw_file_path`, `uploaded_at`, `raw_count`, `valid_count`, `missing_gaps`, `quality_status`)
- `raw_readings` (`id PK`, `dataset_id FK`, `row_index`, `meter_id_raw`, `timestamp_raw`, `consumption_raw`)
- `validation_issues` (`id PK`, `dataset_id FK`, `raw_reading_id`, `row_index`, `issue_type`, `severity`, `detail`)
- `normalised_readings` (`id PK`, `dataset_id FK`, `raw_reading_id`, `meter_id`, `timestamp_iso`, `hour_of_day`, `consumption_kwh`, `is_spike`)
- `recommendations` (`rec_id PK`, `dataset_id FK`, `rule_id`, `payload_json`, `feedback`)
- `simulations` (`id PK`, `dataset_id FK`, `request_json`, `result_json`, `updated_at`)
- `chat_messages` (`id PK`, `dataset_id FK`, `role`, `content`, `used_fallback`, `created_at`)

Repository methods enforce `WHERE dataset_id = ? AND customer_id = ?` on every customer query.

---

## 6. API Endpoints (`main.py`)

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Runtime & LLM gateway configuration status |
| `GET` | `/api/tariff` | Read-only active synthetic ToD tariff schedule |
| `POST` | `/api/datasets/upload` | Upload CSV, preserve raw, validate, normalise |
| `POST` | `/api/datasets/load-sample` | Load bundled synthetic sample CSV (`sample_smart_meter.csv` or `sample_with_faults.csv`) |
| `GET` | `/api/datasets/{dataset_id}/validation` | Retrieve validation summary & flagged issues |
| `GET` | `/api/datasets/{dataset_id}/dashboard` | Measured kWh, 24h profile, spikes, ToD bill breakdown |
| `GET` | `/api/datasets/{dataset_id}/recommendations` | 3–5 deterministic recommendations + grounded explanations |
| `POST` | `/api/recommendations/{rec_id}/feedback` | Save 👍/👎 feedback (`up` / `down`) |
| `POST` | `/api/datasets/{dataset_id}/simulate` | Run deterministic what-if simulation |
| `POST` | `/api/datasets/{dataset_id}/chat` | Grounded AI advisor Q&A with deterministic fallback |

---

## 7. Raw and Normalised Data Handling

- Original CSV files are saved to `uploads/{dataset_id}.csv` and raw rows to `raw_readings` before validation.
- Normalised analytics (`M5`, `M6`, `M7`, `M9`) query `normalised_readings` exclusively, ensuring invalid/duplicate rows are excluded while valid spikes remain included and visibly flagged.

---

## 8. Dashboard Analytics and Time-of-Day Calculations (`analytics.py`)

- Computes `total_kwh`, `avg_daily_kwh`, `day_count`, 24-hour average hourly profile (`00`–`23`), and spike count from `normalised_readings`.
- Classifies each reading into local ToD windows based on `timestamp_iso` hour:
  - `night`: 23:00–06:00
  - `morning`: 06:00–12:00
  - `afternoon`: 12:00–18:00
  - `peak`: 18:00–23:00

---

## 9. Deterministic Tariff and Bill Calculation (`billing.py`)

- Uses read-only synthetic ToD tariff config (illustrative PoC rates in ₹/kWh: Night `6.20`, Morning `8.00`, Afternoon `7.40`, Evening Peak `10.50`).
- Calculates exact cost per window (`window_kwh * rate`) and sums total estimated bill. Zero LLM involvement.

---

## 10. Recommendation Generation and Evidence (`recommendations.py`)

- Deterministic rules inspect peak share, evening load, overnight baseline, and spike flags to generate 3–4 ranked recommendations.
- Each recommendation computes exact monthly kWh & ₹ savings via `billing.py`, attaches a confidence level (`High` / `Medium` / `Estimate` based on day count and data quality), states assumptions and limitations (including non-guaranteed annual projection note), and retrieves matching citations from a small static synthetic KB dictionary (`BESCOM-ToD-2026`, `BEE-AC-24C`, `STANDBY-AUDIT`).

---

## 11. What-If Simulation and Appliance Shifting (`simulation.py`)

- Uses simple selector/button controls for declared synthetic appliances (`Washing Machine`, `Water Heater`, `Dishwasher`, `EV Charger`) across ToD windows, plus AC setpoint (`20`–`27°C`), peak AC trim (`0`–`4 hrs`), and standby reduction (`0`–`100%`).
- Appliance kWh values are explicitly labelled as **estimated appliance-level consumption** (not measured sub-metering).
- Annual savings are labelled as **non-guaranteed projections** (`monthly_savings * 12`) with short-history limitations.

---

## 12. LLM Orchestration, Grounding and Deterministic Fallback (`ai_advisor.py`)

- Uses `openai` SDK configured via `.env` (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`) with a strict timeout (`10s`).
- Injects verified JSON snapshot (`DashboardResponse`, active `SimulationResponse`, `Recommendations`, static KB snippets) into the system prompt.
- **Grounding Rule:** LLM is instructed never to invent numbers; post-check verifies basic safety/non-empty response.
- **Deterministic Fallback:** If `LLM_API_KEY` is unset, gateway is unreachable, or request fails/times out, `ai_advisor.py` returns a deterministic template answer built directly from `analytics.py`, `billing.py`, `simulation.py`, and `recommendations.py` with `used_fallback=True`.

---

## 13. Error Handling, Configuration and Logging

- `.env.example` documents `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `SPIKE_THRESHOLD_KWH`, `DB_PATH`, `UPLOAD_DIR`.
- Structured Python `logging` emits request IDs, `dataset_id`, validation counts, AI fallback events, and latencies.

---

## 14. Synthetic-Data Isolation

- Every customer endpoint requires `customer_id` (default `CUST_DEMO_01`) and verifies `(dataset_id, customer_id)` ownership in `db.py`.
- Requests for a `dataset_id` belonging to a different `customer_id` return `HTTP 404` / `403`.

---

## 15. Demo Deployment and Run Instructions

1. Build React frontend (`frontend/` → `frontend/dist/`).
2. Start FastAPI single-application server: `python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`.
3. Open `http://localhost:8000` in browser and walk through Demo Journey steps 1–9.
