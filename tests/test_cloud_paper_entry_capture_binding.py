"""Offline PAPER regression: each ranked entry must share the captured quote instant.

All receipts here are synthetic fixtures. This is NOT authenticated broker,
cloud deployment, order-execution or matured-outcome evidence.
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import test_cloud_paper_receipt_freshness as fixtures
from test_cloud_paper_run_lineage import rewrite_hash_consistent_payload


class EntryCaptureBindingTests(unittest.TestCase):
    def run_case(self, mutate=None, expected=None):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, proof = Path(tmp) / "runtime", Path(tmp) / "proof"
            runtime.mkdir()

            def child(*args, **kwargs):
                fixtures.make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                if mutate is not None:
                    # Rehash prediction, receipt, entry and DNA after mutation.
                    rewrite_hash_consistent_payload(runtime, mutate)
                return SimpleNamespace(returncode=0)

            if expected:
                with self.assertRaisesRegex(RuntimeError, expected):
                    fixtures.CurrentRunReceiptTests().run_once(runtime, proof, child)
                self.assertNotEqual(
                    json.loads((proof / "status.json").read_text())["status"],
                    "PAPER_RECEIPT_VERIFIED",
                )
            else:
                self.assertEqual(
                    fixtures.CurrentRunReceiptTests().run_once(runtime, proof, child), 0
                )
                self.assertEqual(
                    json.loads((proof / "status.json").read_text())["status"],
                    "PAPER_RECEIPT_VERIFIED",
                )

    def test_valid_entry_capture_passes(self):
        self.run_case()

    def test_same_instant_different_timezone_passes(self):
        def mutate(payload):
            stamp = datetime.fromisoformat(payload["source_timestamp"])
            payload["ranking"][0]["entry_captured_at"] = stamp.astimezone(
                ZoneInfo("Asia/Kolkata")
            ).isoformat()
        self.run_case(mutate)

    def test_missing_capture_fails_even_with_consistent_hashes(self):
        self.run_case(
            lambda p: p["ranking"][0].pop("entry_captured_at"),
            "RANK_ENTRY_CAPTURE_INVALID",
        )

    def test_naive_or_malformed_capture_fails(self):
        for value in (None, "not-a-timestamp", "2026-10-25T09:15:00"):
            with self.subTest(value=value):
                self.run_case(
                    lambda p, v=value: p["ranking"][0].__setitem__(
                        "entry_captured_at", v
                    ),
                    "RANK_ENTRY_CAPTURE_INVALID",
                )

    def test_past_or_future_entry_capture_fails(self):
        for seconds in (-60, 60):
            with self.subTest(seconds=seconds):
                def mutate(payload, delta=seconds):
                    stamp = datetime.fromisoformat(payload["source_timestamp"])
                    payload["ranking"][0]["entry_captured_at"] = (
                        stamp + timedelta(seconds=delta)
                    ).isoformat()
                self.run_case(mutate, "RANK_ENTRY_CAPTURE_MISMATCH")

    def test_wrong_or_missing_exchange_fails(self):
        for value in ("NSE", "BSE", "", None):
            with self.subTest(value=value):
                self.run_case(
                    lambda p, v=value: p["ranking"][0].__setitem__("exchange", v),
                    "RANK_ENTRY_EXCHANGE_INVALID",
                )
        self.run_case(
            lambda p: p["ranking"][0].pop("exchange"),
            "RANK_ENTRY_EXCHANGE_INVALID",
        )


if __name__ == "__main__":
    unittest.main()
