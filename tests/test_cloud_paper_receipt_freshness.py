"""Regression: a successful child exit must not certify an old PAPER receipt.

No broker connection, network request, or real order is made by these tests.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cloud_runner import main as runner
from phase2.daily_close import canonical_hash

FLAGS = {"PAPER_MODE": "1", "LIVE_ORDER_AUTHORITY": "0", "REAL_BROKER_ORDERS": "0"}
CREDS = {
    "ANGEL_API_KEY": "DUMMY", "ANGEL_CLIENT_CODE": "DUMMY",
    "ANGEL_PIN": "DUMMY", "ANGEL_TOTP_SEED": "DUMMY",
}


def make_receipt(runtime, captured_at):
    payload = {"created_at": captured_at, "source_timestamp": captured_at,
               "mode": "PAPER", "live_order_authority": 0, "ranking": []}
    digest = canonical_hash(payload)
    payload["prediction_hash"] = digest
    receipt = {
        "status": "LOCAL_ARTIFACT_ONLY_NOT_INSERTED", "paper_mode": 1,
        "live_order_authority": 0, "prediction_hash": digest,
        "bigquery_merge_parameters": {
            "payload": json.dumps(payload, sort_keys=True), "hash": digest,
        },
    }
    ledger = runtime / "data" / "paper_ledger"
    dna = runtime / "data" / "anomaly_logs"
    ledger.mkdir(parents=True, exist_ok=True)
    dna.mkdir(parents=True, exist_ok=True)
    (ledger / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    evidence = {"prediction_hash": digest, "paper_mode": 1, "live_order_authority": 0}
    (ledger / ("entry_" + digest + ".json")).write_text(json.dumps(evidence), encoding="utf-8")
    (dna / ("dna_" + digest + ".json")).write_text(json.dumps(evidence), encoding="utf-8")
    return digest


class CurrentRunReceiptTests(unittest.TestCase):
    def run_once(self, runtime, proof, child):
        with patch.dict(os.environ, {**FLAGS, **CREDS, "CLOUD_PAPER_RUNTIME_DIR": str(runtime)}, clear=True):
            with patch.object(sys, "argv", ["cloud_runner/main.py", "--once"]):
                with patch.object(runner, "PROOF", proof):
                    with patch.object(runner, "git", side_effect=lambda root, *args:
                                      "test-framework" if args[:2] == ("branch", "--show-current") else "testsha"):
                        with patch.object(runner.subprocess, "run", side_effect=child):
                            return runner.main()

    def test_unchanged_preexisting_receipt_cannot_be_reported_as_fresh(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            make_receipt(runtime, datetime.now(timezone.utc).isoformat())
            with self.assertRaisesRegex(RuntimeError, "RECEIPT_NOT_REFRESHED"):
                self.run_once(runtime, proof, lambda *a, **k: SimpleNamespace(returncode=0))
            self.assertNotEqual(json.loads((proof / "status.json").read_text())["status"],
                                "PAPER_RECEIPT_VERIFIED")

    def test_old_issuance_timestamp_is_not_a_current_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            old = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            with self.assertRaisesRegex(RuntimeError, "RECEIPT_NOT_FROM_CURRENT_RUN"):
                self.run_once(runtime, proof, lambda *a, **k:
                              (make_receipt(runtime, old), SimpleNamespace(returncode=0))[1])

    def test_naive_issuance_timestamp_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            naive = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            with self.assertRaisesRegex(RuntimeError, "RECEIPT_TIMESTAMP_INVALID"):
                self.run_once(runtime, proof, lambda *a, **k:
                              (make_receipt(runtime, naive), SimpleNamespace(returncode=0))[1])

    def test_future_issuance_timestamp_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            with self.assertRaisesRegex(RuntimeError, "RECEIPT_NOT_FROM_CURRENT_RUN"):
                self.run_once(runtime, proof, lambda *a, **k:
                              (make_receipt(runtime, future), SimpleNamespace(returncode=0))[1])

    def test_child_failure_replaces_prior_success_status(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            proof.mkdir()
            (proof / "status.json").write_text('{"status":"PAPER_RECEIPT_VERIFIED"}')
            self.assertEqual(self.run_once(runtime, proof,
                                           lambda *a, **k: SimpleNamespace(returncode=19)), 19)
            result = json.loads((proof / "status.json").read_text())
            self.assertEqual(result["status"], "FAIL_CLOSED")
            self.assertEqual(result["child_exit_code"], 19)
            self.assertEqual(result["broker_order_audit"], "NOT_PERFORMED")

    def test_new_time_bound_receipt_is_accepted_as_local_artifact_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            def child(*a, **k):
                make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                return SimpleNamespace(returncode=0)
            self.assertEqual(self.run_once(runtime, proof, child), 0)
            result = json.loads((proof / "status.json").read_text())
            self.assertEqual(result["status"], "PAPER_RECEIPT_VERIFIED")
            self.assertEqual(result["broker_order_audit"], "NOT_PERFORMED")


if __name__ == "__main__":
    unittest.main()
