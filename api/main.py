"""FastAPI REST API for EnergyWise AI Option B PoC (port 8000)."""

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from energywise.agent.agent import run_agent
from energywise.config import APPLIANCE_ESTIMATES, ENERGYWISE_DB, KB_DIR, LITELLM_API_KEY, USE_MCP
from energywise.engines import tools
from energywise.ingest.ingest import ingest_csv_stream

app = FastAPI(title="EnergyWise AI Option B PoC", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SimulateBody(BaseModel):
    cust_ref: str
    actions: List[Dict[str, Any]] = []


class ChatBody(BaseModel):
    cust_ref: str
    question: str
    actions: Optional[List[Dict[str, Any]]] = None


class FeedbackBody(BaseModel):
    cust_ref: str
    rec_id: str
    rating: str


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "architecture": "Option B",
        "use_mcp": USE_MCP,
        "llm_configured": bool(LITELLM_API_KEY),
    }


@app.get("/customers")
def list_customers() -> List[Dict[str, Any]]:
    if not ENERGYWISE_DB.exists():
        return []
    with sqlite3.connect(str(ENERGYWISE_DB)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT cust_ref, segment, quality_score FROM profiles ORDER BY cust_ref ASC").fetchall()
        return [dict(r) for r in rows]


@app.get("/dashboard/{cust_ref}")
def get_dashboard(cust_ref: str, period: str = Query(default="30d")) -> Dict[str, Any]:
    try:
        summary = tools.get_usage_summary(cust_ref, period=period)
        tariff = tools.get_tariff(cust_ref)
        fc = tools.forecast(cust_ref)
        cands = tools.get_recommendation_candidates(cust_ref)
        return {
            "summary": summary,
            "tariff": tariff,
            "forecast": fc,
            "recommendations": cands,
            "appliances": APPLIANCE_ESTIMATES,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/simulate")
def simulate(body: SimulateBody) -> Dict[str, Any]:
    try:
        sim = tools.simulate_scenario(body.cust_ref, body.actions)
        fc = tools.forecast(body.cust_ref, actions=body.actions)
        return {"simulation": sim, "forecast": fc}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/advice/{cust_ref}")
def advice(cust_ref: str) -> Dict[str, Any]:
    return run_agent(
        cust_ref=cust_ref,
        question="Summarise my top energy-saving recommendations with exact savings.",
        action_type="advice",
    )


@app.post("/chat")
def chat(body: ChatBody) -> Dict[str, Any]:
    return run_agent(
        cust_ref=body.cust_ref,
        question=body.question,
        action_type="chat",
        active_actions=body.actions,
    )


@app.post("/feedback")
def feedback(body: FeedbackBody) -> Dict[str, Any]:
    with sqlite3.connect(str(ENERGYWISE_DB)) as conn:
        conn.execute(
            "INSERT INTO feedback (cust_ref, rec_id, rating, created_at) VALUES (?, ?, ?, ?)",
            (body.cust_ref, body.rec_id, body.rating, datetime.now(timezone.utc).isoformat()),
        )
    return {"status": "saved", "cust_ref": body.cust_ref, "rec_id": body.rec_id, "rating": body.rating}


@app.post("/upload")
async def upload(cust_ref: Optional[str] = Query(default=None), file: UploadFile = File(...)) -> Dict[str, Any]:
    raw = await file.read()
    try:
        return ingest_csv_stream(raw, cust_ref=cust_ref)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/admin/aggregates")
def admin_aggregates() -> Dict[str, Any]:
    with sqlite3.connect(str(ENERGYWISE_DB)) as conn:
        conn.row_factory = sqlite3.Row
        segs = conn.execute(
            "SELECT segment, COUNT(*) as meters, ROUND(AVG(quality_score), 1) as avg_quality "
            "FROM profiles GROUP BY segment"
        ).fetchall()
        fb = conn.execute(
            "SELECT rating, COUNT(*) as cnt FROM feedback GROUP BY rating"
        ).fetchall()
        return {
            "segments": [dict(s) for s in segs],
            "feedback_counts": {r["rating"]: r["cnt"] for r in fb},
        }


@app.get("/admin/documents")
def admin_documents() -> List[Dict[str, str]]:
    return tools._parse_kb_docs(KB_DIR)


@app.get("/admin/audit")
def admin_audit() -> List[Dict[str, Any]]:
    with sqlite3.connect(str(ENERGYWISE_DB)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, cust_ref, action, grounding_json, created_at FROM audit ORDER BY id DESC LIMIT 25"
        ).fetchall()
        return [dict(r) for r in rows]
