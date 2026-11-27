# EnergyWise AI — Option B EIL USP Addendum

| Attribute | Value |
| :--- | :--- |
| **Document ID** | `EW-LLD-OPTB-USP-1.0` |
| **Version** | `1.0` |
| **Date** | 2026-11-27 |
| **Base Commit** | `9e2c8df` (Frozen Option B PoC Baseline) |
| **Feature Branch** | `feature/eil-usp-demo` |

---

## 1. USP & User Journey

**Product Proposition:** *EnergyWise doesn't just tell consumers how much electricity they use. It explains where savings opportunities exist, recommends what to change, demonstrates the projected impact, and helps consumers commit to an actionable plan.*

**Four-Step Demo Journey (`Discover → Decide → Simulate → Commit`):**
1. **Discover:** Inspect evidence-backed consumption opportunities derived from existing analytics (`get_usage_summary`) and recommendation candidates (`get_recommendation_candidates`).
2. **Decide:** Review clear action cards with rationale, projected benefit, qualitative effort level (`Low` / `Medium`), and assumptions/limitations.
3. **Simulate:** Run the existing deterministic what-if simulator (`POST /simulate`) and view baseline vs. proposed kWh, ₹ bill, and CO₂ delta—explicitly labelled **Projected**.
4. **Commit:** Add selected actions to **My Energy Action Plan** and update their status (`Planned` → `Accepted` → `Completed`).

---

## 2. In-Scope Functionality & Explicit Exclusions

- **In Scope:**
  - Enhanced Opportunity/Action cards reusing `dash.recommendations` and `dash.summary`.
  - Existing simulator display with explicit **Projected** labels and assumptions.
  - **My Energy Action Plan** panel with add-to-plan and status updates (`Planned`, `Accepted`, `Completed`) persisted per `cust_ref` in SQLite (`action_plan_items` table).
  - Read-only **Verify Savings — Planned Future Capability** roadmap indicator.
- **Explicitly Out of Scope:**
  - Full 10-entity EIL schema, new MCP tools or `contracts.py` changes, new agent/LLM capabilities, live LLM gateway calls, device control, weather/occupancy attribution, or actual savings verification.

---

## 3. UI Changes & User Interactions (`web/app/page.tsx`)

- **Intelligence Loop Strip:** Visual stage progression (`1. Discover → 2. Decide → 3. Simulate → 4. Commit → 5. Verify [Planned Roadmap]`).
- **Opportunity & Action Cards:** Show opportunity evidence (`pattern`), why it matters (`TAR-ILL-001` / cooling / standby rationale), qualitative effort badge (`Low Effort` / `Medium Effort`), estimate/assumption disclaimer, and **`+ Add to Plan`** button.
- **Simulator Panel:** Retains existing D-9 controls and displays **Projected** savings (`₹`, `kWh`, `CO₂`) and active assumptions.
- **My Energy Action Plan Panel:** Displays committed items for the selected `cust_ref` with status selector buttons (`Planned`, `Accepted`, `Completed`).

---

## 4. Existing Components & APIs Reused

- **Unchanged Engines & Contracts:** `energywise/contracts.py` (`v2.0`), `energywise/engines/tools.py` (`get_usage_summary`, `get_tariff`, `get_recommendation_candidates`, `simulate_scenario`, `forecast`, `search_kb`), `energywise/agent/*` (`Rules Mode` + `privacy.scan()` + `grounding.check()`).
- **Reused Endpoints:** `GET /dashboard/{cust_ref}`, `POST /simulate`, `POST /chat`, `POST /upload`, `GET /admin/*`.
- **New Minimal Endpoints (`api/main.py`):**
  - `GET /action-plan/{cust_ref}`
  - `POST /action-plan/{cust_ref}`
  - `PATCH /action-plan/{cust_ref}/{item_id}`

---

## 5. Minimal Data / State Handling

- Reuses `data/energywise.db` with one additive, self-initialising table `action_plan_items` (`id PK`, `cust_ref`, `rec_id`, `title`, `rationale`, `projected_inr_saving`, `projected_kwh_saving`, `status`, `updated_at`) created via `CREATE TABLE IF NOT EXISTS`—requiring zero database migrations or changes to `ingest.py`.

---

## 6. Projected Savings Calculation Source & Assumptions

- All displayed kWh, `₹`, and CO₂ savings come directly from `energywise/engines/tools.py` (`get_recommendation_candidates` and `simulate_scenario`) using `TAR-ILL-001` and `CO2_KG_PER_KWH = 0.82`.
- All simulation and action-plan benefits are explicitly labelled **Projected** (not achieved or verified) and note that appliance-level figures are customer-declared/benchmark estimates.

---

## 7. Privacy, Customer Isolation & Audit Considerations

- Action-plan queries filter strictly by `cust_ref` (`WHERE cust_ref = ?`); `PATCH` verifies `(id, cust_ref)` ownership (`404` on mismatch).
- Zero PII is stored in `action_plan_items`; `data/pii_vault.db` and `privacy.scan()` remain unchanged.

---

## 8. Acceptance Criteria

1. Existing dashboard, recommendations, and simulator produce unchanged `9e2c8df` baseline results.
2. Opportunity/action cards display consumption evidence, rationale, effort level, and assumptions.
3. User can add an action to **My Energy Action Plan** and update status (`Planned` / `Accepted` / `Completed`).
4. Projected savings are never labelled actual or verified savings.
5. `cust_ref` isolation holds on `/action-plan/*` endpoints.
6. Existing core tests + new action-plan tests pass; `next build` succeeds.

---

## 9. Future Roadmap: Verify Savings

- **Verify Savings (Phase 2/3 Roadmap):** Comparing post-intervention meter readings against a locked baseline using normalised comparisons, completeness/comparability checks, and external confounder attribution remains a planned future capability and is clearly marked as roadmap-only in the UI.
