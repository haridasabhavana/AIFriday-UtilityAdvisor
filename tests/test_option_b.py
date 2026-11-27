"""Unit and FastAPI TestClient integration tests for EnergyWise AI Option B PoC."""

import unittest
from fastapi.testclient import TestClient

from api.main import app
from energywise.agent import grounding, privacy
from energywise.config import hour_to_window, rate_for_hour
from energywise.ingest.ingest import ingest_csv_stream


class OptionBTests(unittest.TestCase):
    def test_tariff_tar_ill_001_windows(self) -> None:
        self.assertEqual(hour_to_window(18), "peak")
        self.assertEqual(hour_to_window(21), "peak")
        self.assertEqual(hour_to_window(22), "shoulder")
        self.assertEqual(hour_to_window(23), "off_peak")
        self.assertEqual(hour_to_window(5), "off_peak")
        self.assertEqual(hour_to_window(6), "standard")
        self.assertEqual(rate_for_hour(19), 10.20)
        self.assertEqual(rate_for_hour(22), 7.50)
        self.assertEqual(rate_for_hour(1), 6.00)

    def test_privacy_scan_redacts_user_and_blocks_system(self) -> None:
        msgs = [
            {"role": "system", "content": "Customer ref C001"},
            {"role": "user", "content": "Call me at 9876543210 or user@example.com for MTR-1001"},
        ]
        scanned = privacy.scan(msgs)
        self.assertIn("[REDACTED_PHONE]", scanned[1]["content"])
        self.assertIn("[REDACTED_EMAIL]", scanned[1]["content"])
        self.assertIn("[REDACTED_METER_ID]", scanned[1]["content"])

        bad_msgs = [{"role": "tool", "content": "meter_id=MTR-1001"}]
        with self.assertRaises(privacy.PrivacyViolationError):
            privacy.scan(bad_msgs)

    def test_grounding_check_number_matching(self) -> None:
        tool_out = [{"total_kwh": 593.9, "peak_window": "18:00-22:00", "delta": {"cost_inr": -147.2}}]
        kb_out = [{"text": "Peak tariff is 10.20 from 18:00 to 22:00."}]
        reply = "1. Your total is 594 kWh and saves ₹147. Peak starts at 18:00."
        res = grounding.check(reply, tool_out, kb_outputs=kb_out)
        self.assertTrue(res["grounded"])
        self.assertEqual(res["ungrounded"], [])

        bad_reply = "You will save ₹9999 per month."
        bad_res = grounding.check(bad_reply, tool_out, kb_outputs=kb_out)
        self.assertFalse(bad_res["grounded"])
        self.assertIn(9999.0, bad_res["ungrounded"])

    def test_csv_upload_aliases_and_api_endpoints(self) -> None:
        client = TestClient(app)
        h = client.get("/health")
        self.assertEqual(h.status_code, 200)
        self.assertEqual(h.json()["architecture"], "Option B")

        custs = client.get("/customers")
        self.assertEqual(custs.status_code, 200)
        self.assertGreaterEqual(len(custs.json()), 100)

        dash = client.get("/dashboard/C001")
        self.assertEqual(dash.status_code, 200)
        self.assertIn("forecast", dash.json())

        sim = client.post(
            "/simulate",
            json={
                "cust_ref": "C001",
                "actions": [
                    {"type": "shift_load", "pct": 20},
                    {"type": "ac_hours", "hours": 1.0},
                    {"type": "reduce_load", "pct": 15},
                    {"type": "shift_kwh", "appliance_id": "wm", "from_window": "peak", "to_window": "off_peak"},
                ],
            },
        )
        self.assertEqual(sim.status_code, 200)
        self.assertLess(sim.json()["simulation"]["delta"]["cost_inr"], 0)
        self.assertLess(sim.json()["simulation"]["delta"]["co2_kg"], 0)

        chat = client.post("/chat", json={"cust_ref": "C001", "question": "Why is my bill high?"})
        self.assertEqual(chat.status_code, 200)
        self.assertTrue(chat.json()["grounding"]["grounded"])

        # Test CSV upload with timestamp/consumption_kwh aliases
        csv_bytes = (
            "meter_id,timestamp,consumption_kwh\n"
            "MTR-9999,2026-11-01T00:00:00+05:30,0.42\n"
            "MTR-9999,2026-11-01T19:00:00+05:30,1.55\n"
        ).encode("utf-8")
        up = client.post("/upload?cust_ref=C099", files={"file": ("sample.csv", csv_bytes, "text/csv")})
        self.assertEqual(up.status_code, 200)
        self.assertEqual(up.json()["cust_ref"], "C099")

        # Admin endpoints
        self.assertEqual(client.get("/admin/aggregates").status_code, 200)
        self.assertEqual(len(client.get("/admin/documents").json()), 6)
        self.assertGreaterEqual(len(client.get("/admin/audit").json()), 1)


if __name__ == "__main__":
    unittest.main()
