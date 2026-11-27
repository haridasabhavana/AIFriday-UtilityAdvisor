"""Ingest synthetic smart-meter CSVs, clean/flag, pseudonymise meter_id -> cust_ref, and populate PII vault."""

import csv
import io
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from energywise.config import ENERGYWISE_DB, PII_VAULT_DB, RAW_SYNTH_DIR, SPIKE_THRESHOLD_KWH


def init_databases(
    energywise_db: Path = ENERGYWISE_DB,
    pii_vault_db: Path = PII_VAULT_DB,
) -> None:
    energywise_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(pii_vault_db)) as pconn:
        pconn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pii_customers (
                cust_ref TEXT PRIMARY KEY,
                meter_id TEXT UNIQUE NOT NULL,
                name TEXT,
                email TEXT,
                phone TEXT,
                address TEXT
            );
            """
        )

    with sqlite3.connect(str(energywise_db)) as econn:
        econn.executescript(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                cust_ref TEXT PRIMARY KEY,
                segment TEXT NOT NULL,
                quality_score REAL NOT NULL,
                raw_count INTEGER NOT NULL DEFAULT 0,
                valid_count INTEGER NOT NULL DEFAULT 0,
                flagged_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS raw_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cust_ref TEXT NOT NULL,
                row_index INTEGER NOT NULL,
                meter_id_raw TEXT,
                ts_raw TEXT,
                kwh_raw TEXT
            );
            CREATE TABLE IF NOT EXISTS validation_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cust_ref TEXT NOT NULL,
                row_index INTEGER,
                issue_type TEXT NOT NULL,
                detail TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cust_ref TEXT NOT NULL,
                ts TEXT NOT NULL,
                hour_of_day INTEGER NOT NULL,
                kwh REAL NOT NULL,
                is_spike INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_readings_cust_ts ON readings(cust_ref, ts);
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cust_ref TEXT NOT NULL,
                rec_id TEXT NOT NULL,
                rating TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cust_ref TEXT NOT NULL,
                action TEXT NOT NULL,
                request_json TEXT NOT NULL,
                tool_calls_json TEXT NOT NULL,
                grounding_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def ingest_csv_stream(
    csv_bytes: bytes,
    cust_ref: Optional[str] = None,
    segment: str = "High-Rise Apartment",
    energywise_db: Path = ENERGYWISE_DB,
    pii_vault_db: Path = PII_VAULT_DB,
) -> Dict[str, Any]:
    """Ingest uploaded CSV (accepting meter_id, ts/timestamp, kwh/consumption_kwh) for a customer."""
    init_databases(energywise_db, pii_vault_db)
    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("Missing CSV header row.")

    headers = {h.strip() for h in reader.fieldnames if h}
    ts_col = "ts" if "ts" in headers else ("timestamp" if "timestamp" in headers else None)
    kwh_col = "kwh" if "kwh" in headers else ("consumption_kwh" if "consumption_kwh" in headers else None)
    if "meter_id" not in headers or not ts_col or not kwh_col:
        raise ValueError("CSV must include meter_id, ts (or timestamp), and kwh (or consumption_kwh).")

    rows = list(reader)
    if not rows:
        raise ValueError("CSV contains zero data rows.")

    first_meter = (rows[0].get("meter_id") or "MTR-UPLOAD").strip()
    target_ref = cust_ref or _resolve_or_create_cust_ref(first_meter, pii_vault_db)

    raw_records = []
    issues = []
    clean_records = []
    seen_ts = set()
    spike_count = 0

    for idx, r in enumerate(rows, start=1):
        m_raw = (r.get("meter_id") or "").strip()
        t_raw = (r.get(ts_col) or "").strip()
        k_raw = (r.get(kwh_col) or "").strip()
        raw_records.append((target_ref, idx, m_raw, t_raw, k_raw))

        try:
            ts_dt = datetime.fromisoformat(t_raw)
        except ValueError:
            issues.append((target_ref, idx, "INVALID_TIMESTAMP", f"Invalid timestamp '{t_raw}'"))
            continue

        try:
            kwh_val = float(k_raw)
        except ValueError:
            issues.append((target_ref, idx, "NON_NUMERIC", f"Non-numeric kWh '{k_raw}'"))
            continue

        if kwh_val < 0:
            issues.append((target_ref, idx, "NEGATIVE_VALUE", f"Negative reading {kwh_val} kWh excluded"))
            continue

        ts_iso = ts_dt.isoformat()
        if ts_iso in seen_ts:
            issues.append((target_ref, idx, "DUPLICATE_TIMESTAMP", f"Duplicate timestamp {ts_iso}"))
            continue
        seen_ts.add(ts_iso)

        is_spike = 1 if kwh_val > SPIKE_THRESHOLD_KWH else 0
        if is_spike:
            spike_count += 1
            issues.append((target_ref, idx, "EXTREME_SPIKE", f"Spike {kwh_val:.2f} kWh (> {SPIKE_THRESHOLD_KWH}) flagged"))

        clean_records.append((target_ref, ts_iso, ts_dt.hour, round(kwh_val, 4), is_spike))

    clean_records.sort(key=lambda x: x[1])
    total = len(raw_records)
    quality_score = round(max(0.0, 100.0 - (len(issues) / max(1, total)) * 100.0), 1)

    with sqlite3.connect(str(energywise_db)) as conn:
        conn.execute("DELETE FROM readings WHERE cust_ref = ?", (target_ref,))
        conn.execute("DELETE FROM raw_readings WHERE cust_ref = ?", (target_ref,))
        conn.execute("DELETE FROM validation_issues WHERE cust_ref = ?", (target_ref,))
        conn.execute(
            "INSERT OR REPLACE INTO profiles (cust_ref, segment, quality_score, raw_count, valid_count, flagged_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (target_ref, segment, quality_score, total, len(clean_records), len(issues)),
        )
        conn.executemany(
            "INSERT INTO raw_readings (cust_ref, row_index, meter_id_raw, ts_raw, kwh_raw) VALUES (?, ?, ?, ?, ?)",
            raw_records,
        )
        if issues:
            conn.executemany(
                "INSERT INTO validation_issues (cust_ref, row_index, issue_type, detail) VALUES (?, ?, ?, ?)",
                issues,
            )
        if clean_records:
            conn.executemany(
                "INSERT INTO readings (cust_ref, ts, hour_of_day, kwh, is_spike) VALUES (?, ?, ?, ?, ?)",
                clean_records,
            )

    return {
        "cust_ref": target_ref,
        "raw_count": total,
        "valid_count": len(clean_records),
        "flagged_count": len(issues),
        "spike_count": spike_count,
        "quality_score": quality_score,
        "issues": [{"row_index": i[1], "issue_type": i[2], "detail": i[3]} for i in issues[:30]],
    }


def _resolve_or_create_cust_ref(meter_id: str, pii_vault_db: Path) -> str:
    with sqlite3.connect(str(pii_vault_db)) as pconn:
        row = pconn.execute("SELECT cust_ref FROM pii_customers WHERE meter_id = ?", (meter_id,)).fetchone()
        if row:
            return row[0]
        count = pconn.execute("SELECT COUNT(*) FROM pii_customers").fetchone()[0]
        new_ref = f"C{count + 1:03d}"
        pconn.execute(
            "INSERT INTO pii_customers (cust_ref, meter_id, name, email, phone, address) VALUES (?, ?, ?, ?, ?, ?)",
            (new_ref, meter_id, "Uploaded Synthetic User", None, None, None),
        )
        return new_ref


def ingest_synthetic_bundle(
    energywise_db: Path = ENERGYWISE_DB,
    pii_vault_db: Path = PII_VAULT_DB,
) -> int:
    """Ingest generated synthetic_cis.csv and synthetic_readings.csv into SQLite + PII vault."""
    init_databases(energywise_db, pii_vault_db)
    cis_path = RAW_SYNTH_DIR / "synthetic_cis.csv"
    readings_path = RAW_SYNTH_DIR / "synthetic_readings.csv"
    if not cis_path.exists() or not readings_path.exists():
        raise FileNotFoundError("Run `python -m energywise.data.generate` first.")

    meter_to_ref: Dict[str, str] = {}
    ref_to_segment: Dict[str, str] = {}

    with sqlite3.connect(str(pii_vault_db)) as pconn, cis_path.open("r", encoding="utf-8") as cf:
        pconn.execute("DELETE FROM pii_customers")
        for row in csv.DictReader(cf):
            meter_to_ref[row["meter_id"]] = row["cust_ref"]
            ref_to_segment[row["cust_ref"]] = row["segment"]
            pconn.execute(
                "INSERT INTO pii_customers (cust_ref, meter_id, name, email, phone, address) VALUES (?, ?, ?, ?, ?, ?)",
                (row["cust_ref"], row["meter_id"], row["name"], row["email"], row["phone"], row["address"]),
            )

    grouped: Dict[str, List[tuple]] = {ref: [] for ref in ref_to_segment}
    seen: Dict[str, set] = {ref: set() for ref in ref_to_segment}
    flags: Dict[str, int] = {ref: 0 for ref in ref_to_segment}
    totals: Dict[str, int] = {ref: 0 for ref in ref_to_segment}

    with readings_path.open("r", encoding="utf-8") as rf:
        for row in csv.DictReader(rf):
            ref = meter_to_ref.get(row["meter_id"])
            if not ref:
                continue
            totals[ref] += 1
            ts = row["ts"]
            if ts in seen[ref]:
                flags[ref] += 1
                continue
            seen[ref].add(ts)
            kwh = float(row["kwh"])
            is_spike = 1 if kwh > SPIKE_THRESHOLD_KWH else 0
            if is_spike:
                flags[ref] += 1
            hr = datetime.fromisoformat(ts).hour
            grouped[ref].append((ref, ts, hr, kwh, is_spike))

    with sqlite3.connect(str(energywise_db)) as econn:
        econn.execute("DELETE FROM readings")
        econn.execute("DELETE FROM profiles")
        for ref, seg in ref_to_segment.items():
            recs = grouped[ref]
            q_score = round(max(0.0, 100.0 - (flags[ref] / max(1, totals[ref])) * 100.0), 1)
            econn.execute(
                "INSERT INTO profiles (cust_ref, segment, quality_score, raw_count, valid_count, flagged_count) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ref, seg, q_score, totals[ref], len(recs), flags[ref]),
            )
            econn.executemany(
                "INSERT INTO readings (cust_ref, ts, hour_of_day, kwh, is_spike) VALUES (?, ?, ?, ?, ?)",
                recs,
            )

    return len(ref_to_segment)


if __name__ == "__main__":
    n = ingest_synthetic_bundle()
    print(f"Ingested {n} synthetic customers into {ENERGYWISE_DB} and {PII_VAULT_DB}")
