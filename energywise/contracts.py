"""Frozen Tool Contracts v2 for EnergyWise AI Option B PoC."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class UsageSummaryOutput(BaseModel):
    cust_ref: str
    period: str
    day_count: int
    total_kwh: float
    est_cost_inr: float
    peak_kwh: float
    peak_share_pct: float
    baseload_kw: float
    top_hours: List[int]
    anomalies: List[Dict[str, Any]]
    quality_score: float


class TariffOutput(BaseModel):
    cust_ref: str
    plan: str
    peak_window: str
    rates_inr_per_kwh: Dict[str, float]


class RecommendationCandidate(BaseModel):
    id: str
    pattern: str
    action: str
    kwh_saving: float
    inr_saving: float
    confidence: str


class SimulationAction(BaseModel):
    type: Literal["shift_load", "reduce_load", "ac_hours", "shift_kwh"]
    pct: Optional[float] = None
    hours: Optional[float] = None
    kwh: Optional[float] = None
    from_window: Optional[str] = "peak"
    to_window: Optional[str] = "off_peak"
    appliance_id: Optional[str] = None


class ScenarioMetrics(BaseModel):
    kwh: float
    cost_inr: float
    peak_kwh: float
    co2_kg: float


class SimulationOutput(BaseModel):
    cust_ref: str
    baseline: ScenarioMetrics
    scenario: ScenarioMetrics
    delta: ScenarioMetrics
    assumptions: List[str]
    hourly_baseline: List[float]
    hourly_scenario: List[float]


class ForecastOutput(BaseModel):
    cust_ref: str
    next_month_kwh: float
    next_month_cost_inr: float
    method: str
    confidence: str


class KBPassage(BaseModel):
    text: str
    source: str
    doc_type: str
    version: str
    effective_from: str
