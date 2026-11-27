"""Configuration for EnergyWise AI Option B PoC (Decisions D-1 to D-11)."""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
KB_DIR = DATA_DIR / "kb"
RAW_SYNTH_DIR = DATA_DIR / "synthetic"
ENERGYWISE_DB = DATA_DIR / "energywise.db"
PII_VAULT_DB = DATA_DIR / "pii_vault.db"

# Decision D-10: Approved LiteLLM Gateway & Model IDs
LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "https://genailab.tcs.in")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "").strip()
CHAT_MODEL = os.getenv("CHAT_MODEL", "azure/genailab-maas-gpt-4.1")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gemini-3-flash-preview")
EMBED_MODEL = os.getenv("EMBED_MODEL", "azure/genailab-maas-text-embedding-3-large")
USE_MCP = os.getenv("USE_MCP", "1") == "1"
LLM_BUDGET_USD = float(os.getenv("LLM_BUDGET_USD", "25.0"))

# Decision D-6: Synthetic Tariff TAR-ILL-001 (One peak window 18:00-22:00, ToU only)
TARIFF_PLAN_ID = "TAR-ILL-001"
TARIFF_PLAN_NAME = "Illustrative Domestic ToD Tariff (TAR-ILL-001)"
PEAK_WINDOW_LABEL = "18:00-22:00"

TOD_WINDOWS = {
    "off_peak": {"label": "Off-Peak (23:00-06:00)", "rate": 6.00, "hours": [23, 0, 1, 2, 3, 4, 5]},
    "standard": {"label": "Standard (06:00-18:00)", "rate": 7.50, "hours": list(range(6, 18))},
    "peak": {"label": "Peak (18:00-22:00)", "rate": 10.20, "hours": [18, 19, 20, 21]},
    "shoulder": {"label": "Shoulder (22:00-23:00)", "rate": 7.50, "hours": [22]},
}

RATES_BY_WINDOW = {k: v["rate"] for k, v in TOD_WINDOWS.items()}

# Illustrative grid emission factor (kg CO2 / kWh) for FR-18
CO2_KG_PER_KWH = float(os.getenv("CO2_KG_PER_KWH", "0.82"))

# Decision D-9: Declared synthetic appliance estimates (no AC setpoint control)
APPLIANCE_ESTIMATES = [
    {"id": "wm", "name": "Washing Machine", "monthly_kwh": 36.0, "default_window": "peak"},
    {"id": "geyser", "name": "Water Heater", "monthly_kwh": 48.0, "default_window": "peak"},
    {"id": "dish", "name": "Dishwasher", "monthly_kwh": 27.0, "default_window": "peak"},
    {"id": "ev", "name": "EV Home Charger", "monthly_kwh": 90.0, "default_window": "peak"},
]

SPIKE_THRESHOLD_KWH = float(os.getenv("SPIKE_THRESHOLD_KWH", "5.0"))


def hour_to_window(hour: int) -> str:
    """Map hour (0-23) to TAR-ILL-001 ToD window key."""
    if hour in (23, 0, 1, 2, 3, 4, 5):
        return "off_peak"
    if 6 <= hour < 18:
        return "standard"
    if 18 <= hour < 22:
        return "peak"
    return "shoulder"


def rate_for_hour(hour: int) -> float:
    return RATES_BY_WINDOW[hour_to_window(hour)]
