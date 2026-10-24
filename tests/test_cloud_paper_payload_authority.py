"""No-network regression for unsafe but internally hash-consistent PAPER prediction payloads.

The fixture forges hashes only inside a temporary directory. It never connects
to a broker or asserts independent zero-order evidence.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cloud_runner import main as runner
from phase2.daily_close import canonical_hash
from test_cloud_paper_receipt_freshness import make_receipt

FLAGS = {"PAPER_MODE": "1", "LIVE_ORDER_AUTHORITY": "0", "REAL_BROKER_ORDERS": "0"}
CREDS = {"ANGEL_API_KEY": "DUMMY", "ANGEL_CLIENT_CODE": "DUMMY",
         "ANGEL_PIN": "DUMMY", "ANGEL_TOTP_SEED": "DUMMY"}


def emit_hash_consistent_unsafe_payload(runtime, overrides):
    stamp = datetime.now(timezone.utc).isoformat()
    old_hash = make_receipt(runtime, stamp)
    ledger = runtime / "data" / "paper_ledger"
    receipt_path = ledger / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload = json.loads(receipt["bigquery_merge_parameters"]["payload"])
    payload.update(overrides)
    payload.pop("prediction_hash", None)
    new_hash = canonical_hash(payload)
    payload["prediction_hash"] = new_hash
    receipt["prediction_hash"] = new_hash
    receipt["bigquery_merge_parameters"]["hash"] = new_hash
    receipt["bigquery_merge_parameters"]["payload"] = json.dumps(payload, sort_keys=True)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    for directory, prefix in ((ledger, "entry_"),
                              (runtime / "data" / "anomaly_logs", "dna_")):
        old = directory / (prefix + old_hash + ".json")
        evidence = json.loads(old.read_text(encoding="utf-8"))
        evidence["prediction_hash"] = new_hash
        (directory / (prefix + new_hash + ".json")).write_text(
            json.dumps(evidence), encoding="utf-8")
        old.unlink()


class PredictionPayloadAuthorityTests(unittest.TestCase):
    def test_unsafe_hash_consistent_prediction_payload_fails_closed(self):
        unsafe_cases = (
            {"mode": "LIVE"},
            {"mode": "paper"},
            {"live_order_authority": 1},
            {"live_order_authority": True},
            {"real_broker_orders": 1},
            {"real_broker_orders": True},
        )
        for overrides in unsafe_cases:
            with self.subTest(overrides=overrides):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    runtime, proof = root / "runtime", root / "proof"
                    runtime.mkdir()
                    def child(*args, **kwargs):
                        emit_hash_consistent_unsafe_payload(runtime, overrides)
                        return SimpleNamespace(returncode=0)
                    with patch.dict(os.environ, {**FLAGS, **CREDS,
                                               "CLOUD_PAPER_RUNTIME_DIR": str(runtime)}, clear=True):
                        with patch.object(sys, "argv", ["cloud_runner/main.py", "--once"]):
                            with patch.object(runner, "PROOF", proof):
                                with patch.object(runner, "git", side_effect=lambda root, *args:
                                                  "test-framework" if args[:2] == ("branch", "--show-current")
                                                  else "offline-test-sha"):
                                    with patch.object(runner.subprocess, "run", side_effect=child):
                                        with self.assertRaisesRegex(
                                                RuntimeError, "PREDICTION_SAFETY_FAILURE"):
                                            runner.main()
                    self.assertNotEqual(
                        json.loads((proof / "status.json").read_text())["status"],
                        "PAPER_RECEIPT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
