# AIFriday-UtilityAdvisor
AIFriday-UtilityAdvisor

---

## EnergyWise AI — Option B PoC & Intelligence Loop USP

EnergyWise AI is a deterministic, privacy-preserving utility consumption advisor and what-if simulator built for **AI Friday Season 3** (Option B architecture + `Discover → Decide → Simulate → Commit` Intelligence Loop USP).

### Project Structure
- `energywise/` — Core Python packages: `config.py` (`TAR-ILL-001` tariff), `contracts.py` (frozen tool contracts v2), `data/generate.py` (100 synthetic customers × 90 days), `ingest/ingest.py` (CSV ingestion + PII vault), `engines/tools.py` (analytics, billing, recommendations, simulator, forecast, CO₂), `mcp_servers/` (FastMCP stdio servers), `agent/` (`privacy.scan()`, `grounding.check()`, LiteLLM gateway + `rules_mode` fallback).
- `api/main.py` — FastAPI REST backend (port `8000`) including `/action-plan/{cust_ref}` persistence.
- `web/` — Next.js 15 + Tailwind CSS frontend (port `3000`).
- `data/kb/` — 6 approved illustrative Markdown knowledge-base documents.
- `tests/test_option_b.py` — Automated `unittest` + `FastAPI TestClient` suite.
- `DEMO_GUIDE.md` & `EnergyWise_AI_Demo_Presentation.html` — Presenter script & interactive 6-slide HTML deck.

### Quick Start
1. Copy `.env.example` to `.env` (leave `LITELLM_API_KEY` blank for deterministic **Rules Mode**, or add your approved gateway key).
2. Generate and ingest synthetic data:
   ```powershell
   python -m energywise.data.generate
   python -m energywise.ingest.ingest
   ```
3. Start FastAPI backend:
   ```powershell
   python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
   ```
4. Start Next.js frontend:
   ```cmd
   cd web
   set NODE_OPTIONS=--use-system-ca
   npm install
   npm run dev
   ```
5. Open `http://localhost:3000` (and run tests with `python -m unittest discover -s tests -v`).
