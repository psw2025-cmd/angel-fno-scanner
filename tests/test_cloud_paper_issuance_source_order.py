"""Offline regression: forecast issuance must not precede its source capture.

This exercises only synthetic temporary files; it does not authenticate market
data, execute broker orders, or establish cloud deployment.
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import test_cloud_paper_receipt_freshness as fixtures


class IssuanceSourceOrderTests(unittest.TestCase):
    def test_hash_consistent_forecast_issued_before_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, proof = Path(tmp) / "runtime", Path(tmp) / "proof"
            runtime.mkdir()

            def child(*args, **kwargs):
                issued = datetime.now(timezone.utc)
                # Both times are current-run and within existing 5-second
                # future-skew tolerance. Their *order* is impossible for a
                # forward-issued prediction based on this snapshot.
                captured = issued + timedelta(seconds=2)
                fixtures.make_receipt(
                    runtime, issued.isoformat(),
                    source_captured_at=captured.isoformat(),
                    payload_source_at=captured.isoformat(),
                )
                return SimpleNamespace(returncode=0)

            with self.assertRaisesRegex(
                RuntimeError, "PREDICTION_PRECEDES_SOURCE_CAPTURE"
            ):
                fixtures.CurrentRunReceiptTests().run_once(runtime, proof, child)
            self.assertNotEqual(
                json.loads((proof / "status.json").read_text())["status"],
                "PAPER_RECEIPT_VERIFIED",
            )

    def test_source_capture_before_issuance_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, proof = Path(tmp) / "runtime", Path(tmp) / "proof"
            runtime.mkdir()

            def child(*args, **kwargs):
                captured = datetime.now(timezone.utc)
                issued = captured + timedelta(milliseconds=1)
                fixtures.make_receipt(
                    runtime, issued.isoformat(),
                    source_captured_at=captured.isoformat(),
                    payload_source_at=captured.isoformat(),
                )
                return SimpleNamespace(returncode=0)

            self.assertEqual(
                fixtures.CurrentRunReceiptTests().run_once(runtime, proof, child), 0
            )
            self.assertEqual(
                json.loads((proof / "status.json").read_text())["status"],
                "PAPER_RECEIPT_VERIFIED",
            )


    def test_same_instant_with_different_timezone_offsets_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, proof = Path(tmp) / "runtime", Path(tmp) / "proof"
            runtime.mkdir()

            def child(*args, **kwargs):
                instant = datetime.now(timezone.utc)
                local_capture = instant.astimezone(ZoneInfo("Asia/Kolkata"))
                fixtures.make_receipt(
                    runtime, instant.isoformat(),
                    source_captured_at=local_capture.isoformat(),
                    payload_source_at=local_capture.isoformat(),
                )
                return SimpleNamespace(returncode=0)

            self.assertEqual(
                fixtures.CurrentRunReceiptTests().run_once(runtime, proof, child), 0
            )
            self.assertEqual(
                json.loads((proof / "status.json").read_text())["status"],
                "PAPER_RECEIPT_VERIFIED",
            )


if __name__ == "__main__":
    unittest.main()
