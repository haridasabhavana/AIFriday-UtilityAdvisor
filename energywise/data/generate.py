"""Generate 100 synthetic customers, 90 days hourly readings with faults, and fake CIS."""

import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from energywise.config import RAW_SYNTH_DIR

SEGMENTS = ["High-Rise Apartment", "EV Residential", "Independent Villa"]
BASE_PROFILE = [
    0.36, 0.32, 0.30, 0.29, 0.31, 0.38,
    0.54, 0.72, 0.66, 0.56, 0.50, 0.46,
    0.48, 0.52, 0.50, 0.55, 0.64, 0.84,
    1.30, 1.56, 1.50, 1.22, 0.78, 0.48,
]


def generate_all(num_customers: int = 100, days: int = 90, seed: int = 42) -> Path:
    rng = random.Random(seed)
    RAW_SYNTH_DIR.mkdir(parents=True, exist_ok=True)
    tz = timezone(timedelta(hours=5, minutes=30))
    start = datetime(2026, 8, 1, 0, 0, tzinfo=tz)

    cis_path = RAW_SYNTH_DIR / "synthetic_cis.csv"
    readings_path = RAW_SYNTH_DIR / "synthetic_readings.csv"

    with cis_path.open("w", newline="", encoding="utf-8") as cf, readings_path.open(
        "w", newline="", encoding="utf-8"
    ) as rf:
        cis_writer = csv.writer(cf)
        cis_writer.writerow(["meter_id", "cust_ref", "segment", "name", "email", "phone", "address"])

        r_writer = csv.writer(rf)
        r_writer.writerow(["meter_id", "ts", "kwh"])

        for idx in range(1, num_customers + 1):
            meter_id = f"MTR-{1000 + idx}"
            cust_ref = f"C{idx:03d}"
            segment = SEGMENTS[(idx - 1) % len(SEGMENTS)]
            scale = {"High-Rise Apartment": 1.0, "EV Residential": 1.25, "Independent Villa": 1.15}[segment]

            cis_writer.writerow(
                [
                    meter_id,
                    cust_ref,
                    segment,
                    f"Synthetic User {idx:03d}",
                    f"user{idx:03d}@example.invalid",
                    f"90000{idx:05d}",
                    f"{idx} Sample Layout, Bengaluru",
                ]
            )

            for d in range(days):
                for h in range(24):
                    ts = start + timedelta(days=d, hours=h)
                    # Inject a few synthetic faults on early days for quality demo
                    if idx <= 10 and d == 1 and h == 3:
                        continue  # missing interval
                    val = max(0.12, BASE_PROFILE[h] * scale * rng.uniform(0.88, 1.14))
                    if idx <= 10 and d == 2 and h == 20:
                        val = round(val * 4.8, 3)  # spike
                    r_writer.writerow([meter_id, ts.isoformat(), f"{val:.3f}"])
                    if idx <= 5 and d == 0 and h == 5:
                        r_writer.writerow([meter_id, ts.isoformat(), f"{val:.3f}"])  # duplicate

    return readings_path


if __name__ == "__main__":
    out = generate_all()
    print(f"Generated synthetic dataset at {out}")
