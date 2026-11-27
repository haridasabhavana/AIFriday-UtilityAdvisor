"""Deterministic calculation engines and tool REGISTRY (Contracts v2)."""

import math
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from energywise.config import (
    APPLIANCE_ESTIMATES,
    CO2_KG_PER_KWH,
    ENERGYWISE_DB,
    KB_DIR,
    PEAK_WINDOW_LABEL,
    RATES_BY_WINDOW,
    TARIFF_PLAN_ID,
    hour_to_window,
    rate_for_hour,
)


def _fetch_readings(cust_ref: str, days: int = 30, db_path: Path = ENERGYWISE_DB) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        prof = conn.execute("SELECT * FROM profiles WHERE cust_ref = ?", (cust_ref,)).fetchone()
        if not prof:
            raise ValueError(f"Unknown cust_ref '{cust_ref}'")
        rows = conn.execute(
            "SELECT ts, hour_of_day, kwh, is_spike FROM readings WHERE cust_ref = ? ORDER BY ts DESC LIMIT ?",
            (cust_ref, days * 24),
        ).fetchall()
        data = [dict(r) for r in reversed(rows)]
        return dict(prof), data


def get_usage_summary(cust_ref: str, period: str = "30d", db_path: Path = ENERGYWISE_DB) -> Dict[str, Any]:
    days = 90 if period == "90d" else (7 if period == "7d" else 30)
    prof, rows = _fetch_readings(cust_ref, days=days, db_path=db_path)
    if not rows:
        raise ValueError(f"No readings for {cust_ref}")

    total_kwh = 0.0
    est_cost = 0.0
    peak_kwh = 0.0
    hourly_sums = defaultdict(float)
    hourly_counts = defaultdict(int)
    anomalies = []
    distinct_days = set()

    for r in rows:
        kwh = float(r["kwh"])
        hr = int(r["hour_of_day"])
        total_kwh += kwh
        est_cost += kwh * rate_for_hour(hr)
        if hour_to_window(hr) == "peak":
            peak_kwh += kwh
        hourly_sums[hr] += kwh
        hourly_counts[hr] += 1
        distinct_days.add(r["ts"][:10])
        if r["is_spike"]:
            anomalies.append({"ts": r["ts"], "kwh": round(kwh, 2), "type": "EXTREME_SPIKE"})

    hourly_avg = [
        round(hourly_sums[h] / hourly_counts[h], 3) if hourly_counts[h] else 0.0
        for h in range(24)
    ]
    top_hours = sorted(range(24), key=lambda h: hourly_avg[h], reverse=True)[:3]
    baseload_kw = round(min(hourly_avg[0:6]) if any(hourly_avg[0:6]) else min(hourly_avg), 3)
    peak_share_pct = round((peak_kwh / total_kwh) * 100.0, 1) if total_kwh > 0 else 0.0

    return {
        "cust_ref": cust_ref,
        "period": period,
        "day_count": max(1, len(distinct_days)),
        "total_kwh": round(total_kwh, 2),
        "est_cost_inr": round(est_cost, 2),
        "peak_kwh": round(peak_kwh, 2),
        "peak_share_pct": peak_share_pct,
        "baseload_kw": baseload_kw,
        "top_hours": top_hours,
        "anomalies": anomalies[:10],
        "quality_score": prof["quality_score"],
        "hourly_avg": hourly_avg,
    }


def get_tariff(cust_ref: str) -> Dict[str, Any]:
    return {
        "cust_ref": cust_ref,
        "plan": TARIFF_PLAN_ID,
        "peak_window": PEAK_WINDOW_LABEL,
        "rates_inr_per_kwh": RATES_BY_WINDOW,
    }


def get_recommendation_candidates(cust_ref: str, db_path: Path = ENERGYWISE_DB) -> List[Dict[str, Any]]:
    summary = get_usage_summary(cust_ref, period="30d", db_path=db_path)
    day_count = summary["day_count"]
    scale = 30.0 / day_count
    peak_kwh_mo = summary["peak_kwh"] * scale
    total_kwh_mo = summary["total_kwh"] * scale
    night_base_mo = summary["baseload_kw"] * 7.0 * 30.0

    conf = "High" if day_count >= 25 and summary["quality_score"] >= 95 else "Medium"

    # Candidate 1: Shift 25% of peak load to off-peak
    shift_kwh = round(min(peak_kwh_mo * 0.25, 75.0), 1)
    shift_inr = round(shift_kwh * (RATES_BY_WINDOW["peak"] - RATES_BY_WINDOW["off_peak"]), 2)

    # Candidate 2: Trim evening AC runtime by 1 hr/day (~1.2 kW)
    ac_kwh = round(min(peak_kwh_mo * 0.30, 36.0), 1)
    ac_inr = round(ac_kwh * RATES_BY_WINDOW["peak"], 2)

    # Candidate 3: Cut overnight standby by 20%
    standby_kwh = round(min(night_base_mo * 0.20, 24.0), 1)
    standby_inr = round(standby_kwh * RATES_BY_WINDOW["off_peak"], 2)

    return [
        {
            "id": "REC-SHIFT-PEAK",
            "pattern": f"Peak window (18:00-22:00) accounts for {summary['peak_share_pct']}% of usage",
            "action": f"Shift ~{shift_kwh} kWh/month of flexible appliances to Off-Peak (23:00-06:00)",
            "kwh_shift": shift_kwh,
            "kwh_saving": 0.0,
            "inr_saving": shift_inr,
            "confidence": conf,
        },
        {
            "id": "REC-AC-TRIM",
            "pattern": f"Top demand hours occur at {summary['top_hours']} during evening peak",
            "action": "Trim evening AC runtime by 1 hour/day during 18:00-22:00",
            "kwh_saving": ac_kwh,
            "inr_saving": ac_inr,
            "confidence": "Estimate",
        },
        {
            "id": "REC-STANDBY",
            "pattern": f"Continuous overnight baseload of {summary['baseload_kw']} kW",
            "action": "Cut overnight standby load by 20% using smart power strips",
            "kwh_saving": standby_kwh,
            "inr_saving": standby_inr,
            "confidence": conf,
        },
    ]


def simulate_scenario(
    cust_ref: str,
    actions: List[Dict[str, Any]],
    db_path: Path = ENERGYWISE_DB,
) -> Dict[str, Any]:
    summary = get_usage_summary(cust_ref, period="30d", db_path=db_path)
    day_count = summary["day_count"]
    base_hourly = list(summary["hourly_avg"])
    sim_hourly = list(base_hourly)
    assumptions: List[str] = []

    app_map = {a["id"]: a for a in APPLIANCE_ESTIMATES}

    for act in actions:
        atype = act.get("type")
        if atype == "shift_load":
            pct = max(0.0, min(50.0, float(act.get("pct") or 0.0)))
            if pct > 0:
                frac = pct / 100.0
                moved_per_hr = []
                for h in [18, 19, 20, 21]:
                    delta = sim_hourly[h] * frac
                    sim_hourly[h] = max(0.05, sim_hourly[h] - delta)
                    moved_per_hr.append(delta)
                avg_add = sum(moved_per_hr) / 4.0
                for h in [0, 1, 2, 3]:
                    sim_hourly[h] += avg_add
                assumptions.append(f"Shifted {pct:.0f}% of Peak (18:00-22:00) load to Off-Peak (23:00-06:00).")

        elif atype == "shift_kwh":
            app_id = act.get("appliance_id")
            if app_id and app_id in app_map:
                kwh_mo = app_map[app_id]["monthly_kwh"]
                name = app_map[app_id]["name"]
            else:
                kwh_mo = max(0.0, float(act.get("kwh") or 0.0))
                name = "Declared appliance"
            from_w = act.get("from_window") or "peak"
            to_w = act.get("to_window") or "off_peak"
            if kwh_mo > 0 and from_w != to_w:
                win_hours = {
                    "peak": [18, 19, 20, 21],
                    "off_peak": [0, 1, 2, 3],
                    "standard": [10, 11, 14, 15],
                    "shoulder": [22],
                }
                src_hrs = win_hours.get(from_w, [18, 19, 20, 21])
                dst_hrs = win_hours.get(to_w, [0, 1, 2, 3])
                daily_kwh = kwh_mo / 30.0
                for h in src_hrs:
                    sim_hourly[h] = max(0.05, sim_hourly[h] - daily_kwh / len(src_hrs))
                for h in dst_hrs:
                    sim_hourly[h] += daily_kwh / len(dst_hrs)
                assumptions.append(
                    f"Shifted {name} (~{kwh_mo:.0f} kWh/mo estimate) from {from_w} to {to_w}."
                )

        elif atype == "ac_hours":
            hrs = max(0.0, min(4.0, float(act.get("hours") or 0.0)))
            if hrs > 0:
                daily_cut = hrs * 1.2  # illustrative 1.2 kW compressor
                for h in [18, 19, 20, 21]:
                    sim_hourly[h] = max(0.05, sim_hourly[h] - daily_cut / 4.0)
                assumptions.append(f"Trimmed peak AC runtime by {hrs:.1f} hr/day (est. 1.2 kW draw).")

        elif atype == "reduce_load":
            pct = max(0.0, min(30.0, float(act.get("pct") or 0.0)))
            if pct > 0:
                frac = pct / 100.0
                for h in [23, 0, 1, 2, 3, 4, 5]:
                    sim_hourly[h] = max(0.05, sim_hourly[h] * (1.0 - frac))
                assumptions.append(f"Reduced overnight standby load (23:00-06:00) by {pct:.0f}%.")

    def _metrics(hourly_arr: List[float]) -> Dict[str, float]:
        kwh = sum(hourly_arr) * day_count
        cost = sum(hourly_arr[h] * rate_for_hour(h) for h in range(24)) * day_count
        pk = sum(hourly_arr[h] for h in [18, 19, 20, 21]) * day_count
        return {
            "kwh": round(kwh, 2),
            "cost_inr": round(cost, 2),
            "peak_kwh": round(pk, 2),
            "co2_kg": round(kwh * CO2_KG_PER_KWH, 2),
        }

    base_calc = _metrics(base_hourly)
    scen_calc = _metrics(sim_hourly)
    delta_m = {
        "kwh": round(scen_calc["kwh"] - base_calc["kwh"], 2),
        "cost_inr": round(scen_calc["cost_inr"] - base_calc["cost_inr"], 2),
        "peak_kwh": round(scen_calc["peak_kwh"] - base_calc["peak_kwh"], 2),
        "co2_kg": round(scen_calc["co2_kg"] - base_calc["co2_kg"], 2),
    }
    base_m = {
        "kwh": summary["total_kwh"],
        "cost_inr": summary["est_cost_inr"],
        "peak_kwh": summary["peak_kwh"],
        "co2_kg": round(summary["total_kwh"] * CO2_KG_PER_KWH, 2),
    }
    scen_m = {
        "kwh": round(base_m["kwh"] + delta_m["kwh"], 2),
        "cost_inr": round(base_m["cost_inr"] + delta_m["cost_inr"], 2),
        "peak_kwh": round(base_m["peak_kwh"] + delta_m["peak_kwh"], 2),
        "co2_kg": round(base_m["co2_kg"] + delta_m["co2_kg"], 2),
    }

    return {
        "cust_ref": cust_ref,
        "baseline": base_m,
        "scenario": scen_m,
        "delta": delta_m,
        "assumptions": assumptions or ["No scenario changes applied yet."],
        "hourly_baseline": [round(x, 3) for x in base_hourly],
        "hourly_scenario": [round(x, 3) for x in sim_hourly],
    }


def forecast(
    cust_ref: str,
    actions: Optional[List[Dict[str, Any]]] = None,
    db_path: Path = ENERGYWISE_DB,
) -> Dict[str, Any]:
    if actions:
        sim = simulate_scenario(cust_ref, actions, db_path=db_path)
        summary = get_usage_summary(cust_ref, period="30d", db_path=db_path)
        scale = 30.0 / summary["day_count"]
        return {
            "cust_ref": cust_ref,
            "next_month_kwh": round(sim["scenario"]["kwh"] * scale, 2),
            "next_month_cost_inr": round(sim["scenario"]["cost_inr"] * scale, 2),
            "method": "30-day statistical baseline adjusted by active scenario",
            "confidence": "Medium" if summary["day_count"] >= 20 else "Low / Estimate",
        }

    summary = get_usage_summary(cust_ref, period="30d", db_path=db_path)
    scale = 30.0 / summary["day_count"]
    return {
        "cust_ref": cust_ref,
        "next_month_kwh": round(summary["total_kwh"] * scale, 2),
        "next_month_cost_inr": round(summary["est_cost_inr"] * scale, 2),
        "method": "30-day statistical baseline projection",
        "confidence": "Medium" if summary["day_count"] >= 20 else "Low / Estimate",
    }


def _parse_kb_docs(kb_dir: Path = KB_DIR) -> List[Dict[str, str]]:
    docs: List[Dict[str, str]] = []
    if not kb_dir.exists():
        return docs
    for path in sorted(kb_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta: Dict[str, str] = {"source": path.name}
        body = raw
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) == 3:
                for line in parts[1].strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip().strip('"').strip("'")
                body = parts[2].strip()
        if meta.get("status", "").lower() == "published":
            meta["text"] = body
            docs.append(meta)
    return docs


def search_kb(query: str, doc_type: Optional[str] = None, kb_dir: Path = KB_DIR) -> List[Dict[str, str]]:
    docs = _parse_kb_docs(kb_dir)
    if doc_type:
        docs = [d for d in docs if d.get("doc_type") == doc_type]

    tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    scored = []
    for d in docs:
        hay = (d.get("text", "") + " " + d.get("doc_type", "")).lower()
        score = sum(1 for t in tokens if t in hay)
        scored.append((score, d))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for _, d in scored[:3]:
        results.append(
            {
                "text": d["text"][:450],
                "source": d.get("doc_id", d["source"]),
                "doc_type": d.get("doc_type", "general"),
                "version": d.get("version", "1.0"),
                "effective_from": d.get("effective_from", "2026-04-01"),
            }
        )
    return results


def fetch_intervals(meter_ref: str, days: int = 30, db_path: Path = ENERGYWISE_DB) -> Dict[str, Any]:
    """Mock smart-meter API tool (backend sync only; never called by LLM)."""
    return {"meter_ref": meter_ref, "days": days, "status": "ok", "note": "Mock smart-meter API sync"}


REGISTRY: Dict[str, Callable[..., Any]] = {
    "get_usage_summary": get_usage_summary,
    "get_tariff": get_tariff,
    "get_recommendation_candidates": get_recommendation_candidates,
    "simulate_scenario": simulate_scenario,
    "forecast": forecast,
    "search_kb": search_kb,
    "fetch_intervals": fetch_intervals,
}
