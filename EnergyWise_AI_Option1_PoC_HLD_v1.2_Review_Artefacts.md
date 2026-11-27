# EnergyWise AI — Option 1 PoC HLD (v1.3)
## Supporting Review, Remediation, Gap, Decision & Approval Artefacts

**Reference Option 1 HLD:** [EnergyWise_AI_Option1_PoC_HLD_v1.2.md](file:///c:/Users/GenAIBLRANCUSR31/Documents/EnergyWise%20Ai/EnergyWise_AI_Option1_PoC_HLD_v1.2.md) (updated to v1.3)  
**Companion Option 2 Target Architecture:** [EnergyWise_AI_Option2_Enterprise_Target_Architecture.md](file:///c:/Users/GenAIBLRANCUSR31/Documents/EnergyWise%20Ai/EnergyWise_AI_Option2_Enterprise_Target_Architecture.md) (v0.1 Draft)  
**Date:** 2026-11-27  
**Prepared By:** Lead Solution Architect & Technical Design Authority (TDA)

---

## 1. Option 1 vs. Option 2 Integration Comparison

| Area | Option 1 – PoC / Pass 1 | Option 2 – Enterprise Target State *(Planned)* |
| :--- | :--- | :--- |
| **CSV ingestion** | **Primary ingestion method** (agreed synthetic CSV upload via React UI) | May remain as fallback / manual ingestion |
| **Utility connection** | **None required** (no live utility connection, no mock utility API in critical path, no credentials) | Planned provider integration |
| **MCP** | **Not implemented** (no MCP client or MCP server) | Planned integration capability (Pattern 1: Provider MCP Server; Pattern 2: Managed Adapter → MCP) |
| **Data retrieval** | Uploaded CSV | Approved utility-provider resources / tools (subject to consent & allowlisting) |
| **Security** | Controlled synthetic-data demonstration with backend dataset & role isolation | Enterprise identity (OAuth2/OIDC), consent governance, PII Vault & mTLS/secrets management |

---

## 2. HLD Review and Remediation Report (v1.1 → v1.2 → v1.3)

| Finding | Original Review / Integration Finding | Action Taken in Option 1 HLD (v1.2 / v1.3) | HLD Section(s) Updated | Remaining Concern (If Any) |
| :---: | :--- | :--- | :--- | :--- |
| **A** | **Simplify privacy and data handling:** PoC uses synthetic data only; remove unnecessary PII mapping/pseudonymisation vault architecture. | Removed PoC PII Identity Mapping vault/tokenisation; standardised on synthetic identifiers (`customer_id`, `dataset_id`, `meter_id`) with zero real PII. | Sections 1.2, 2.1, 3.1–3.8, 4.1, 5, 8.1, 13 (`ADR-05`) | None for PoC; PII vaulting deferred to Option 2. |
| **B** | **Customer data isolation:** PoC lacks login/auth; enforce dataset isolation on backend and separate Utility/Admin access. | Enforced `customer_id`/`dataset_id` scoping and `role_context` (`customer` vs. `utility_admin`) in `M2` and `M12`; isolated `M11` admin views. | Sections 1.2, 2.1, 3.2–3.7, 4.1–4.6, 5.3, 8.1, 12.1 (`R-04`), 14 | Relies on synthetic `dataset_id`/`role_context` in PoC; replaced by OAuth2/RBAC in Option 2. |
| **C** | **Smart-meter data quality:** Preserve original uploaded file/readings; flag missing/duplicate/negative/out-of-order/anomalous readings; separate traceable remediation; do not invent unconfirmed rules. | Updated `M3`/`M4`/`M12` and Journey A to preserve immutable raw CSV & raw readings, flag issues without silent mutation, store traceable remediation separately, and defer exact thresholds to SME confirmation. | Sections 1.1, 2.1, 3.3, 3.4, 4.1, 5.1, 8.2, 12.2 (`A-05`), 13 (`ADR-06`), 14 | Exact thresholds/scoring weights require SME confirmation (`GAP-01`). |
| **D** | **Consumption measurement clarity:** Separate actual measured, estimated appliance-level, and modelled/inferred consumption. | Added explicit three-way classification across data domains, calculations, journeys, and AI constraints. | Sections 1.2, 4.2–4.4, 5.3, 6, 7.3, 12.1 (`R-03`) | Enforce labels consistently in React UI and AI prompts in LLD. |
| **E & F** | **Recommendation confidence & annual projections:** Define reason, evidence, savings + assumptions, confidence/limitations; label annual savings as non-guaranteed projections. | Defined 5 required recommendation elements and explicit short-history annual projection disclaimers; prohibited LLM arithmetic. | Sections 1.1, 2.1, 4.3, 4.4, 5.1, 6, 7.2, 7.3, 14 | Exact confidence-tier rules to be confirmed in LLD. |
| **G** | **Carbon-emission estimates:** Make CO₂ factor configurable/illustrative if included, or defer/log as open decision. | Made CO₂ factor configurable and illustrative-only if enabled; tracked inclusion in `OD-06`. | Sections 5.1, 6, 11, 14, 15.2 (`OD-06`) | Pending decision on `OD-06`. |
| **H** | **Scalability claims:** Do not claim 100,000+ meter scalability as proven by PoC. | Separated single-node PoC expectations from future enterprise scalability objectives. | Sections 10, 12.2 (`A-02`) | None. |
| **I** | **Technology decisions:** Keep unresolved PoC choices (backend framework, DB, vector store, charting library) as explicit open decisions. | Tracked `OD-01`, `OD-07`, `OD-08`, `OD-09` as explicit open decisions for sign-off before LLD. | Sections 1.2, 7.2, 11, 13 (`ADR-02`), 14, 15.2 | Pending TDA/engineering sign-off. |
| **Part A & B** | **Integration Strategy Update (v1.3):** Option 1 Pass 1 must use **CSV upload only** (no MCP, no mock utility API in critical path); MCP-enabled utility integration is deferred to **Option 2**. | Updated Option 1 HLD to CSV-only ingestion (`M3`, diagrams, Journey A, Section 9, `ADR-07`, `R-05`, `C-03`, 15-point LLD Handover) and created Option 2 Enterprise Target Architecture (`EW-HLD-OPT2-001`) defining planned MCP integration. | Option 1 Sections 1–5, 8.2, 9, 12–15; Option 2 Document | Remove `MCP` badge & `Sync Meter` button when scaffolding Option 1 React UI (`GAP-06`). |

---

## 3. HLD Gap Register

| Gap ID | Description | Severity | Proposed Resolution | Owner | Status |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **GAP-01** | **Unconfirmed Data Quality Thresholds & Scoring Formula:** Exact rules for spike detection, gap-handling limits, and Data Quality Score weighting are not yet confirmed by business SMEs. | High | Present candidate deterministic validation rules at LLD kickoff for SME/Product sign-off (do not invent in HLD). | Product / Domain SME | **Open** |
| **GAP-02** | **Unresolved PoC Implementation Stack (`OD-01`, `OD-07`, `OD-08`, `OD-09`):** Python web framework, local structured DB, vector-store choice, and React charting library are not formally approved. | High | Review recommendations (`FastAPI`, `SQLite`, `Chroma`/lightweight RAG, React charting library) at HLD sign-off meeting. | TDA / Engineering Leads | **Open** |
| **GAP-03** | **CO₂ Inclusion & Approved Grid Emission Factor (`OD-06`):** Decision pending on whether CO₂ estimates appear in PoC and what illustrative/approved factor to configure. | Medium | Confirm `OD-06` during HLD review; if enabled, supply configurable factor and illustrative disclaimer. | Product Lead / Domain SME | **Open** |
| **GAP-04** | **Stretch PoC Prioritisation (`OD-04`):** `FR-09` (forecast), `FR-12` (admin view), `FR-13` (fallback), and `NFR-08` (audit log) need firm PoC vs. stretch confirmation. | Medium | Lock PoC demo scope in `OD-04` prior to LLD/sprint planning. | Delivery Lead / Product Lead | **Open** |
| **GAP-05** | **Approved Synthetic KB, Sample CSV & Tariff Governance Dataset (`OD-02`, `OD-03`):** Final curated synthetic KB documents, agreed PoC sample CSV schema/dataset, and tariff approval metadata need SME validation. | Medium | Domain SME to review synthetic ToD tariff config, KB advisories, and sample CSV format before LLD. | Domain SME / AI Lead | **Open** |
| **GAP-06** | **UI Prototype `MCP` & `Sync Meter` Alignment (`R-05`):** Existing HTML prototype displays an `MCP` badge and `Sync Meter` button, whereas Option 1 Pass 1 uses **CSV upload only** (MCP is deferred to Option 2). | Low | Remove `MCP` badge and `Sync Meter` control when building the Option 1 React UI; replace with CSV upload workflow and status/validation display. | UI Lead | **Open** |

---

## 4. Updated Open Decisions Register

| Decision ID | Description | Recommendation | Impact | Approval Required From | Status |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **OD-01** | **React Charting Library & Appliance Shifting UX** (React is confirmed as UI framework; charting library & drag-and-drop vs. selector UX remain open). | Use a lightweight React charting library and provide accessible click/selector controls alongside optional drag-and-drop matching the prototype. | Determines frontend dependencies and UI component effort in LLD. | UI Lead, Delivery Lead, TDA | **Proposed** |
| **OD-02** | **Admin Tariff Configurator Scope** (Interactive ToD rate editor in PoC vs. read-only approved tariff display). | Show read-only approved tariff schedules and approval metadata (`NFR-12`) in PoC; defer interactive rate editing to Roadmap. | Keeps PoC Admin scope focused and avoids tariff-mutation complexity during demo. | Product Lead, Business SME, TDA | **Proposed** |
| **OD-03** | **RAG Document Corpus & Tool Contracts** (Finalise synthetic KB documents and `search_kb` / `shift_kwh` tool contracts). | Adopt `search_kb(doc_type)` and `shift_kwh` deterministic tool contracts over the curated synthetic KB set. | Defines AI tool schemas and RAG metadata in LLD. | AI Lead, Backend Lead, Domain SME | **Proposed** |
| **OD-04** | **Stretch PoC Prioritisation** (Confirm mandatory vs. stretch scope for `FR-09`, `FR-12`, `FR-13`, `NFR-08`). | Prioritise `FR-13` fallback and `FR-12` read-only aggregate view as core demo pillars; include `FR-09` and `NFR-08` if schedule permits. | Controls PoC sprint scope and demo readiness. | Delivery Lead, Product Lead | **Proposed** |
| **OD-05** | **PoC NFR Target Sign-Off** (Confirm <500 ms sim, <5 s chat, and ~100 profiles × 90 days synthetic scale assumptions). | Approve proposed PoC targets as baseline for LLD sizing and evaluation tests. | Sets acceptance criteria for PoC performance testing. | TDA, QA Lead | **Open** |
| **OD-06** | **CO₂ Emission Estimates in PoC** (Include configurable illustrative CO₂ estimates in PoC vs. defer to Roadmap). | If included, make emission factor configurable via `.env`/config and label output as illustrative until an approved grid factor is supplied; otherwise defer. | Affects simulation result DTOs and UI KPI sub-text. | Product Lead, Domain SME | **Open** |
| **OD-07** | **Python Backend Framework** (Select Python web/API framework for `M2` serving React SPA and REST/JSON endpoints). | Recommend **FastAPI** for typed Pydantic DTO alignment and seamless reuse in Option 2 three-tier Target architecture. | Governs backend API scaffolding, validation, and static-asset serving in LLD. | Backend Lead, TDA | **Proposed** |
| **OD-08** | **PoC Database / Storage Technology** (Select local structured storage engine for `M12`). | Recommend **SQLite** (abstracted behind repository interfaces in `M12`) for zero-setup PoC portability. | Determines physical schema DDL and query layer in LLD. | Backend Lead, Data Lead, TDA | **Proposed** |
| **OD-09** | **Vector-Store Technology (If Required)** (Select local vector store vs. lightweight metadata/keyword retrieval for curated KB). | Recommend lightweight local vector store (e.g., **Chroma**) only if semantic retrieval is needed beyond metadata filtering; abstract behind `M12`. | Affects PoC dependencies, indexing step, and local deployment footprint. | AI Lead, TDA | **Proposed** |

---

## 5. Consistency & Readiness Report

- **Option 1 Cross-Check (CSV-Only Scope):** Verified all diagrams (`3.1`, `3.3`, `3.4`, `3.8`), module descriptions (`M2`, `M3`, `M12`), Journey A, Integration Boundaries (Section 9), `ADR-07`, `R-05`, `C-03`, Traceability Matrix (`15.1`), and the 15-point LLD Handover (Section 14) consistently specify **CSV upload only** for Option 1 Pass 1 with **no MCP client/server** and **no utility-provider credentials or connections**.
- **Option 2 Cross-Check (Planned MCP Integration):** Verified [EnergyWise_AI_Option2_Enterprise_Target_Architecture.md](file:///c:/Users/GenAIBLRANCUSR31/Documents/EnergyWise%20Ai/EnergyWise_AI_Option2_Enterprise_Target_Architecture.md) clearly labels MCP utility-provider integration as a **planned target-state capability**, supports both Pattern 1 (provider MCP server) and Pattern 2 (managed adapter → MCP), enforces enterprise security/consent/allowlisting, and keeps all calculations deterministic.
- **Readiness Verdict:** **Option 1 HLD (v1.3) is ready for stakeholder review and conditional sign-off.** Option 1 LLD must **not** be baselined or started until HLD approval and resolution of `OD-01`–`OD-09` and `GAP-01`–`GAP-02`.

---

## 6. HLD Approval Checklist (Option 1)

| # | Approval Criterion | Assessment in Option 1 HLD (v1.3) | Sign-Off Status |
| :-: | :--- | :--- | :---: |
| **1** | **Business scope confirmed** | PoC capabilities (`1`–`10`) with **CSV-only ingestion** in Pass 1 and clear separation from Option 2 MCP integration (Section 1, Section 9). | `[ ] Pending Stakeholder Sign-Off` |
| **2** | **Architecture agreed** | Modular single-deployable Option 1 architecture (React SPA + Python backend `M2`–`M12`) preserved with clear evolution path to Option 2 (Sections 2, 3, 13, 14.1). | `[ ] Pending TDA Sign-Off` |
| **3** | **Module responsibilities clear** | All 12 logical modules have unambiguous responsibilities; `M3` scoped strictly to CSV ingestion with no MCP dependency (Sections 2, 3). | `[ ] Pending TDA Sign-Off` |
| **4** | **Data and AI boundaries clear** | Deterministic code (`M4`–`M9`) owns all numbers; measured vs. estimated vs. modelled consumption separated; LLM limited to grounded explanation/chat with fallback (Sections 5, 6, 7). | `[ ] Pending TDA & AI Lead Sign-Off` |
| **5** | **Security and privacy approach agreed** | Synthetic-only PoC data model (no real PII); backend-enforced `customer_id`/`dataset_id` isolation and `role_context` separation (Section 8.1). | `[ ] Pending Security & TDA Sign-Off` |
| **6** | **Data quality approach agreed** | Original CSV file and raw readings preserved untouched; issues flagged; transformations stored separately and traceably; thresholds deferred to SME sign-off (Section 8.2). | `[ ] Pending Domain SME Sign-Off` |
| **7** | **NFRs reviewed** | PoC performance expectations separated from unvalidated future enterprise scalability; proposed targets tagged as assumptions (Section 10). | `[ ] Pending QA & TDA Sign-Off` |
| **8** | **Risks and assumptions reviewed** | Risks (`R-01`–`R-06`), Assumptions (`A-01`–`A-05`), and Constraints (`C-01`–`C-04`) documented with mitigations and owners (Section 12). | `[ ] Pending Delivery & TDA Sign-Off` |
| **9** | **Open decisions acknowledged** | All unresolved scope, rule, and technology choices (`OD-01`–`OD-09`) explicitly listed with recommendations, impacts, and approvers (Section 15.2). | `[ ] Pending Stakeholder Sign-Off` |
| **10** | **HLD ready for LLD** | Option 1 HLD (v1.3) is internally consistent and ready for CSV-only LLD handover **upon formal HLD approval and resolution of `OD-01`–`OD-09` and `GAP-01`–`GAP-02`** (Section 14). | `[ ] Ready for Approval Gate` |
