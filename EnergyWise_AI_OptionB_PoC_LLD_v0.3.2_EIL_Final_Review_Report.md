# EnergyWise AI — Option B LLD v0.3.2 (EIL)
## Final Technical Review & Sign-Off Report

**Reviewed Specification:** [EnergyWise_AI_OptionB_PoC_LLD_v0.3.2.md](file:///c:/Users/GenAIBLRANCUSR31/Documents/EnergyWise%20Ai/EnergyWise_AI_OptionB_PoC_LLD_v0.3.2.md) (`EW-LLD-OPTB-003.2`, v0.3.2)  
**Baseline Reference:** [EnergyWise_AI_OptionB_PoC_LLD_v0.2.md](file:///c:/Users/GenAIBLRANCUSR31/Documents/EnergyWise%20Ai/EnergyWise_AI_OptionB_PoC_LLD_v0.2.md) | Frozen Git Checkpoint: `9e2c8df` *(Untouched)*  
**Date:** 2026-11-27

---

## 1. Executive Verdict

**Verdict: APPROVE FOR IMPLEMENTATION (Phase 1 First, on Branch `feature/energywise-intelligence-loop` off `9e2c8df`)**

All four MAJOR technical findings (`F-01`–`F-04`) and three MINOR findings (`F-05`–`F-07`) identified during the technical review of `v0.3.1` have been resolved in **`v0.3.2`**. The design is internally consistent, 100% backward-compatible with frozen Option B baseline `9e2c8df`, preserves deterministic backend math, and enforces honest, non-causal savings verification.

---

## 2. Comparison Against v0.3.1

| Area | v0.3.1 State | v0.3.2 Improvement |
| :--- | :--- | :--- |
| **Entity Linkage & Edge Cases** | `SimulationScenario` lacked `int_ids[]`; `SavingsVerificationResult` lacked `plan_id`/`attributed_item_ids[]`; abandoned workflows unspecified. | Added explicit FKs, state-transition rules, and declined/ephemeral workflow guards (`F-01`). |
| **Causal `verified_savings`** | Defined `verified_savings` without explicitly deferring it from Phase 2 PoC. | Explicitly deferred causal `verified_savings` to **Phase 3**; added 12-factor attribution table (`F-02`). |
| **Calculation & Anti-Double-Counting** | Mentioned anti-double-counting in prose without formula or worked example. | Added exact equations, sequential reduction-then-shift capping, and 2 worked examples (`F-03`). |
| **Contract Consistency** | Minor field-name (`post_start` vs `period_start`) and sign inconsistencies. | Standardised ISO 8601 + timezone, `INR`/`kWh`/`kg`, sign conventions, and `400`/`404`/`422` errors (`F-04`). |
| **Module DAG & Retention** | Module dependency direction and PoC retention/reset unspecified. | Defined strict acyclic DAG (`F-05`) and PoC reset/consent controls (`F-06`). |

---

## 3. Findings & Remediation Log

| Finding ID | Severity | Description | Resolution in v0.3.2 | Status |
| :--- | :---: | :--- | :--- | :---: |
| **F-01** | **MAJOR** | Missing FKs (`SimulationScenario.int_ids[]`, `SavingsVerificationResult.plan_id`/`attributed_item_ids[]`) and unspecified abandoned/declined action-plan handling. | Added FKs, lifecycle transition rules, and `422` guard preventing baseline lock on all-declined plans (§15.1–§15.2). | **Closed** |
| **F-02** | **MAJOR** | Causal `verified_savings` lacked explicit Phase 3 deferral despite Phase 2 PoC lacking weather/occupancy/control-group data. | Deferred `verified_savings` to Phase 3; Phase 2 PoC emits `verification_pending`, `inconclusive`, or `observed_change` only (§13.2). | **Closed** |
| **F-03** | **MAJOR** | Anti-double-counting and normalised 60d vs. 30d verification lacked explicit formulas and worked examples. | Added equations, sequential reduction-then-shift capping, and `C001` worked examples (§16.2). | **Closed** |
| **F-04** | **MAJOR** | `post_start` vs `period_start` field-name mismatch and `saving` vs `delta` sign inconsistency in example JSON. | Standardised `period_start`/`period_end`, positive `saving` vs. signed `delta`, and HTTP error codes (§15.2). | **Closed** |
| **F-05** | **MINOR** | Potential circular dependency risk between `tools.py` and new EIL engine modules. | Enforced strict acyclic DAG (`tools.py` never imports EIL modules) (§14.1). | **Closed** |
| **F-06** | **MINOR** | PoC data retention/deletion and user-consent boundaries for action-plan mutations not stated. | Documented PoC `ingest.py` reset/retention and UI-only mutation rules (§19). | **Closed** |
| **F-07** | **MINOR** | Needed explicit assessment of Phase 1 standalone competition demo value without Phase 2. | Confirmed Phase 1 (`DISCOVER → DECIDE → SIMULATE → ACT`) is a complete standalone demo (§21). | **Closed** |
| **AR-01** | **ACCEPTED RISK** | Live LLM gateway model authorisation (`azure/genailab-maas-gpt-4.1`, `gemini-3-flash-preview`) and `verify=False` TLS in `llm.py` remain open in the separate compliance audit. | **Accepted for Rules-Mode PoC**; live LLM mode remains unapproved until closed in the separate audit (§2, §19). | **Tracked** |

---

## 4. Technical Domain Reviews

- **Architecture Review:** Cleanly reuses `tools.py`, `engines_server.py`, `agent.py`, `privacy.py`, `grounding.py`, `energywise.db`, and Next.js 15 + FastAPI with zero new infrastructure or external MCP.
- **Calculation Integrity Review:** Peak-shifting (`ΔkWh = 0`) vs. load-reduction (`ΔkWh < 0`) mathematically separated; sequential capping prevents double-counting; `scenario = baseline + delta` preserves `₹0.00` reconciliation.
- **Verification & Attribution Review:** All 12 attribution factors assessed; `80%` completeness = preliminary check; `7d` = `early_7d`, `>= 28d` = `strong_28d`; Phase 2 strictly reports `observed_change` (never causal `verified_savings`).
- **API / MCP Contract Review:** `v2.1-eil` adds 4 read-only MCP tools without altering frozen `v2.0` contracts; v2.0 regression suite mandatory before Phase 1 merge.
- **Privacy & Security Review:** `cust_ref` isolation, `pii_vault.db` separation, `privacy.scan()`, audit logging, and no autonomous device control all preserved. Separate AI Friday audit findings (`verify=False`, live model slugs) remain explicitly open.
- **UX & Demonstration Review:** 6 views with mandatory provenance badges (`MEASURED`, `ESTIMATED`, `PROJECTED`, `OBSERVED CHANGE (SYNTHETIC DEMO)`, `INCONCLUSIVE`/`VERIFICATION PENDING`, `VERIFIED SAVINGS` Phase 3 only); `C001` 60d vs. 30d demo uses normalised rates and synthetic disclaimers.

---

## 5. Phase 1 Feasibility & D-1..D-11 Traceability

- **Phase 1 Feasibility:** High (~2–3 dev days). Delivers `DISCOVER → DECIDE → SIMULATE → ACT` end-to-end with high visual/business impact even before Phase 2 `VERIFY`.
- **D-1 to D-11 Traceability:** 100% aligned (Option B, MCP, number-level grounding, PII vault, `TAR-ILL-001`, Next.js + FastAPI, CO₂/forecast/admin/audit, D-9 simulator controls, gateway/KB rules).
- **Acceptance-Test Coverage:** All 15 acceptance scenarios (`AT-01`–`AT-15` in §20) trace directly to `EIL-01`–`EIL-05`, `EIL-OD-01`, `EIL-OD-02`, and `EIL-A-01`.

---

## 6. Outstanding Decisions, Risks & Approval Recommendation

- **Remaining Decisions / External Audit Items:** Formal sign-off on `EW-LLD-OPTB-003.2` (`v0.3.2`) to open branch `feature/energywise-intelligence-loop` from `9e2c8df`; separate compliance audit closure required before enabling live LLM gateway mode (`AR-01`).
- **Recommendation:** **APPROVE FOR IMPLEMENTATION** — proceed to Phase 1 on `feature/energywise-intelligence-loop` off `9e2c8df` upon explicit user sign-off.
