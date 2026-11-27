# EnergyWise AI — Option B LLD v0.3.1 (EIL)
## Review Corrections, Decision Log & Gate Readiness Report

**Target LLD:** [EnergyWise_AI_OptionB_PoC_LLD_v0.3.1.md](file:///c:/Users/GenAIBLRANCUSR31/Documents/EnergyWise%20Ai/EnergyWise_AI_OptionB_PoC_LLD_v0.3.1.md) (`EW-LLD-OPTB-003.1`, v0.3.1)  
**Frozen Demo Baseline:** Git commit `9e2c8df` *(Untouched)*  
**Date:** 2026-11-27

---

## 1. Decision Log (EIL Open Decisions & Corrections)

| ID | Topic | Disposition | Summary of Resolution in v0.3.1 |
| :--- | :--- | :---: | :--- |
| **EIL-OD-01** | **Additive MCP Contracts (`v2.1-eil`)** | **Revised** *(Pending Gate Sign-Off)* | Retained the 4 additive, read-only, deterministic MCP tools (`discover_opportunities`, `rank_interventions`, `get_intelligence_loop_summary`, `get_savings_verification`) under explicit `v2.1-eil` versioning, backward-compatible with all 7 existing D-2 `v2.0` tools, with `cust_ref` isolation and mandatory v2.0 regression tests. |
| **EIL-OD-02** | **Verification Thresholds & Comparability** | **Revised** *(Pending Gate Sign-Off)* | Kept `80%` completeness as a configurable preliminary threshold (not a verification guarantee); `7 days` = early observation only; `>= 28 days` preferred for stronger comparison; added weekday/weekend, ToD-window, and missing-interval comparability checks; distinguished `verification_pending`, `inconclusive`, `observed_change`, and strictly gated `verified_savings`. |
| **EIL-A-01** | **`C001` Synthetic Demo (Days 1–60 vs. 61–90)** | **Revised** *(Pending Gate Sign-Off)* | Retained Days 1–60 baseline vs. Days 61–90 illustrative period using **normalised** (daily / 30-day equivalent) comparison, ToD & weekday/weekend checks, explicit synthetic-data labelling, and no causal or actual-customer claims. |
| **EIL-AI** | **AI Friday Compliance Wording** | **Revised** *(Tracked in Separate Audit)* | Removed unconditional AI Friday PASS claim; documented that EIL adds no external service/model dependency, while live LLM gateway authorisation and `verify=False` TLS remediation remain open in the separate compliance audit. |

---

## 2. AI Friday Compliance Statement (Corrected)

- **EIL Design Impact:** EIL introduces **no additional external service, endpoint, or model dependency** beyond the existing Option B baseline.
- **Separate Audit Tracking:** Existing AI Friday compliance findings are tracked in the separate compliance audit:
  1. Exact live LLM gateway model authorisation (`azure/genailab-maas-gpt-4.1`, `gemini-3-flash-preview`, `azure/genailab-maas-text-embedding-3-large` on `https://genailab.tcs.in`) remains **unverified** live.
  2. The reported `verify=False` TLS configuration in `energywise/agent/llm.py` **requires remediation** before live gateway use.
- **Approval Boundary:** Live LLM mode **must not** be described as approved until the separate compliance audit closes these findings.

---

## 3. Compatibility & Baseline Integrity Check

- **D-1 to D-11 Compatibility:** All 11 team decisions remain intact. Existing `contracts.py` v2.0 tools and FastAPI endpoints are preserved without breaking changes.
- **Frozen Judging Baseline (`9e2c8df`):** **Zero impact.** No application code, dependency, database migration, or gateway call was executed.
- **Branching Plan (Post-Approval Only):** Once v0.3.1 is explicitly approved, create branch `feature/energywise-intelligence-loop` from `9e2c8df` before starting Phase 1 implementation.
