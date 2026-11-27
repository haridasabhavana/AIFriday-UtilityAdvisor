"""Option B tool-calling agent with MCP tools, privacy.scan, grounding.check, and rules mode."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from energywise.agent import grounding, llm, mcp_client, privacy
from energywise.config import ENERGYWISE_DB, USE_MCP

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_usage_summary",
            "description": "Get measured smart-meter usage summary, peak share, baseload, anomalies, and quality score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cust_ref": {"type": "string"},
                    "period": {"type": "string", "enum": ["7d", "30d", "90d"]},
                },
                "required": ["cust_ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tariff",
            "description": "Get ToD tariff rates (TAR-ILL-001) and peak window.",
            "parameters": {
                "type": "object",
                "properties": {"cust_ref": {"type": "string"}},
                "required": ["cust_ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recommendation_candidates",
            "description": "Get deterministic recommendation candidates with kWh and INR savings.",
            "parameters": {
                "type": "object",
                "properties": {"cust_ref": {"type": "string"}},
                "required": ["cust_ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_scenario",
            "description": "Simulate what-if actions (shift_load, reduce_load, ac_hours, shift_kwh).",
            "parameters": {
                "type": "object",
                "properties": {
                    "cust_ref": {"type": "string"},
                    "actions": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["cust_ref", "actions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forecast",
            "description": "Forecast next month kWh and INR cost.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cust_ref": {"type": "string"},
                    "actions": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["cust_ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": "Search approved utility knowledge base documents for explanations and policy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "doc_type": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
]


def _rules_mode_reply(cust_ref: str, question: str, active_actions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Deterministic Option C fallback inside Option B."""
    summary = mcp_client.call_tool("get_usage_summary", {"cust_ref": cust_ref, "period": "30d"}, use_mcp=False)
    tariff = mcp_client.call_tool("get_tariff", {"cust_ref": cust_ref}, use_mcp=False)
    cands = mcp_client.call_tool("get_recommendation_candidates", {"cust_ref": cust_ref}, use_mcp=False)
    kb = mcp_client.call_tool("search_kb", {"query": question or "peak tariff"}, use_mcp=False)
    tool_outputs: List[Any] = [summary, tariff, cands]

    q = question.lower()
    unsupported_keywords = ("weather", "refund", "dispute", "wiring", "repair", "competitor", "stock", "cricket", "news", "solar panel quote")
    if any(k in q for k in unsupported_keywords):
        reply = (
            "[Rules Mode] I cannot answer that from your smart-meter readings or approved tariff documents. "
            "I can only assist with your measured consumption, TAR-ILL-001 bill breakdown, what-if savings "
            "simulations, next-month baseline forecast, and approved energy-efficiency guidance."
        )
    elif "forecast" in q or "next month" in q:
        fc = mcp_client.call_tool("forecast", {"cust_ref": cust_ref, "actions": active_actions}, use_mcp=False)
        tool_outputs.append(fc)
        reply = (
            f"[Rules Mode] Next month forecast for {cust_ref}: {fc['next_month_kwh']} kWh "
            f"(₹{fc['next_month_cost_inr']}) using {fc['method']} (confidence: {fc['confidence']})."
        )
    elif active_actions:
        sim = mcp_client.call_tool("simulate_scenario", {"cust_ref": cust_ref, "actions": active_actions}, use_mcp=False)
        tool_outputs.append(sim)
        reply = (
            f"[Rules Mode] Over {summary['day_count']} days, baseline usage is {summary['total_kwh']} kWh "
            f"(₹{summary['est_cost_inr']}). Your active scenario changes usage to {sim['scenario']['kwh']} kWh "
            f"(₹{sim['scenario']['cost_inr']}), a delta of ₹{sim['delta']['cost_inr']} and "
            f"{sim['delta']['co2_kg']} kg CO2."
        )
    else:
        top = cands[0]
        reply = (
            f"[Rules Mode] Over {summary['day_count']} days, measured usage is {summary['total_kwh']} kWh "
            f"(₹{summary['est_cost_inr']}) under {tariff['plan']}, with {summary['peak_share_pct']}% in Peak "
            f"({tariff['peak_window']} at ₹{tariff['rates_inr_per_kwh']['peak']}/kWh). Top action: {top['action']} "
            f"to save ₹{top['inr_saving']}/month."
        )

    g_res = grounding.check(reply, tool_outputs, kb_outputs=kb, user_text=question)
    return {
        "reply": reply,
        "mode": "rules_mode",
        "tool_calls": ["get_usage_summary", "get_tariff", "get_recommendation_candidates"],
        "grounding": g_res,
        "citations": [k["source"] for k in kb],
    }


def _write_audit(
    cust_ref: str,
    action: str,
    scanned_messages: List[Dict[str, Any]],
    tool_calls: List[Dict[str, Any]],
    grounding_res: Dict[str, Any],
    db_path: Path = ENERGYWISE_DB,
) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO audit (cust_ref, action, request_json, tool_calls_json, grounding_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                cust_ref,
                action,
                json.dumps(scanned_messages),
                json.dumps(tool_calls),
                json.dumps(grounding_res),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def run_agent(
    cust_ref: str,
    question: str,
    action_type: str = "chat",
    active_actions: Optional[List[Dict[str, Any]]] = None,
    db_path: Path = ENERGYWISE_DB,
) -> Dict[str, Any]:
    """Run Option B tool-calling loop with privacy.scan, grounding.check, and rules-mode fallback."""
    system_prompt = (
        "You are EnergyWise AI (Option B). You MUST call tools to retrieve all numbers. "
        "NEVER invent or compute numbers yourself. Only state numbers returned by tool outputs. "
        f"Active customer pseudonym: {cust_ref}. Never ask for or output personal data."
    )
    user_prompt = question
    if active_actions:
        user_prompt += f"\n(Active simulator actions for context: {json.dumps(active_actions)})"

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    tool_outputs: List[Any] = []
    kb_outputs: List[Any] = []
    logged_tools: List[Dict[str, Any]] = []

    try:
        scanned = privacy.scan(messages)
        reply_text = ""

        for _ in range(6):
            resp = llm.call_llm(scanned, tools=OPENAI_TOOLS)
            msg = resp.choices[0].message
            if msg.tool_calls:
                scanned.append(msg.model_dump(exclude_none=True))
                for tc in msg.tool_calls:
                    tname = tc.function.name
                    targs = json.loads(tc.function.arguments or "{}")
                    if "cust_ref" in targs or tname != "search_kb":
                        targs["cust_ref"] = cust_ref  # enforce cust_ref isolation
                    result = mcp_client.call_tool(tname, targs, use_mcp=USE_MCP)
                    if tname == "search_kb":
                        kb_outputs.append(result)
                    else:
                        tool_outputs.append(result)
                    logged_tools.append({"tool": tname, "args": targs, "result": result})
                    scanned.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result),
                        }
                    )
                scanned = privacy.scan(scanned)
            else:
                reply_text = (msg.content or "").strip()
                break

        if not reply_text:
            raise RuntimeError("Agent completed loop without text reply")

        g_res = grounding.check(reply_text, tool_outputs, kb_outputs=kb_outputs, user_text=question)
        if not g_res["grounded"]:
            # Regenerate once on grounding mismatch
            scanned.append(
                {
                    "role": "user",
                    "content": (
                        f"Your previous reply contained ungrounded numbers {g_res['ungrounded']}. "
                        "Rewrite using ONLY exact numbers from tool outputs."
                    ),
                }
            )
            scanned = privacy.scan(scanned)
            retry_resp = llm.call_llm(scanned)
            reply_text = (retry_resp.choices[0].message.content or "").strip()
            g_res = grounding.check(reply_text, tool_outputs, kb_outputs=kb_outputs, user_text=question)
            if not g_res["grounded"]:
                raise RuntimeError(f"Grounding failed after retry: {g_res['ungrounded']}")

        _write_audit(cust_ref, action_type, scanned, logged_tools, g_res, db_path=db_path)
        return {
            "reply": reply_text,
            "mode": "llm_grounded",
            "tool_calls": [t["tool"] for t in logged_tools],
            "grounding": g_res,
            "citations": [k["source"] for batch in kb_outputs if isinstance(batch, list) for k in batch],
        }

    except Exception:
        fallback = _rules_mode_reply(cust_ref, question, active_actions=active_actions)
        _write_audit(cust_ref, f"{action_type}_fallback", privacy.scan(messages), logged_tools, fallback["grounding"], db_path=db_path)
        return fallback
