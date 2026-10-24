"""Regression: a successful child exit must not certify an old PAPER receipt.

No broker connection, network request, or real order is made by these tests.
"""
import hashlib
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


def make_receipt(runtime, captured_at, *, source_captured_at=None, payload_source_at=None,
                 source_kind="ANGEL_SMARTAPI_READONLY_QUOTES_NOT_OFFICIAL_SETTLEMENT",
                 payload_source_kind=None, quotes=None):
    # Synthetic fixture shaped like a broker capture; never authentic market evidence.
    if quotes is None:
        # This is a synthetic fixture, never a broker receipt. Keep it valid
        # against the quote-exchange-time gate so unrelated negative tests
        # reach the safety condition they are explicitly testing.
        try:
            quote_stamp = datetime.fromisoformat(source_captured_at or captured_at)
            if quote_stamp.tzinfo is None:
                quote_stamp = quote_stamp.replace(tzinfo=timezone.utc)
            feed_time = quote_stamp.astimezone(
                __import__("zoneinfo").ZoneInfo("Asia/Kolkata")
            ).strftime("%d-%b-%Y %H:%M:%S")
        except (TypeError, ValueError):
            feed_time = "23-Oct-2026 09:15:00"
        quotes = [{"contract": {"tradingsymbol": "OFFLINE_TEST_ONLY",
                                 "symboltoken": "999"},
                   "quote": {"tradingSymbol": "OFFLINE_TEST_ONLY",
                             "symbolToken": "999",
                             "exchFeedTime": feed_time}}]
    snapshot = {"captured_at": source_captured_at or captured_at,
                "source_kind": source_kind, "quotes": quotes}
    raw_path = runtime / "data" / "raw_snapshot.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_bytes = (json.dumps(snapshot, sort_keys=True) + "\n").encode("utf-8")
    raw_path.write_bytes(raw_bytes)
    source_hash = hashlib.sha256(raw_bytes).hexdigest()
    payload = {"created_at": captured_at, "source_timestamp": payload_source_at or captured_at,
               "source_hash": source_hash,
               "mode": "PAPER", "live_order_authority": 0, "ranking": [],
               "provenance": {"source_kind": payload_source_kind or source_kind}}
    digest = canonical_hash(payload)
    payload["prediction_hash"] = digest
    receipt = {
        "status": "LOCAL_ARTIFACT_ONLY_NOT_INSERTED", "paper_mode": 1,
        "live_order_authority": 0, "prediction_hash": digest,
        "source_hash": payload["source_hash"],
        "bigquery_merge_parameters": {
            "payload": json.dumps(payload, sort_keys=True), "hash": digest,
        },
    }
    ledger = runtime / "data" / "paper_ledger"
    dna = runtime / "data" / "anomaly_logs"
    ledger.mkdir(parents=True, exist_ok=True)
    dna.mkdir(parents=True, exist_ok=True)
    (ledger / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    evidence = {"prediction_hash": digest, "source_hash": payload["source_hash"],
                "paper_mode": 1, "live_order_authority": 0}
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


    def test_boolean_flags_in_receipt_are_rejected_not_coerced(self):
        # In Python True == 1 and False == 0; JSON booleans are not valid integer flags.
        for key, value in (("paper_mode", True), ("live_order_authority", False)):
            with self.subTest(flag=key):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    runtime, proof = root / "runtime", root / "proof"
                    runtime.mkdir()
                    def child(*args, **kwargs):
                        make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                        path = runtime / "data" / "paper_ledger" / "receipt.json"
                        receipt = json.loads(path.read_text(encoding="utf-8"))
                        receipt[key] = value
                        path.write_text(json.dumps(receipt), encoding="utf-8")
                        return SimpleNamespace(returncode=0)
                    with self.assertRaisesRegex(RuntimeError, "RECEIPT_SAFETY_FAILURE"):
                        self.run_once(runtime, proof, child)

    def test_boolean_flags_in_linked_evidence_are_rejected(self):
        for key, value in (("paper_mode", True), ("live_order_authority", False)):
            with self.subTest(flag=key):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    runtime, proof = root / "runtime", root / "proof"
                    runtime.mkdir()
                    def child(*args, **kwargs):
                        digest = make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                        path = runtime / "data" / "paper_ledger" / ("entry_" + digest + ".json")
                        evidence = json.loads(path.read_text(encoding="utf-8"))
                        evidence[key] = value
                        path.write_text(json.dumps(evidence), encoding="utf-8")
                        return SimpleNamespace(returncode=0)
                    with self.assertRaisesRegex(RuntimeError, "LINKED_EVIDENCE_INVALID"):
                        self.run_once(runtime, proof, child)



    def test_receipt_source_hash_must_match_prediction_payload(self):
        # A valid prediction hash must not mask a contradictory receipt source.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            def child(*args, **kwargs):
                make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                path = runtime / "data" / "paper_ledger" / "receipt.json"
                receipt = json.loads(path.read_text(encoding="utf-8"))
                receipt["source_hash"] = "b" * 64
                path.write_text(json.dumps(receipt), encoding="utf-8")
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "SOURCE_PROVENANCE_MISMATCH"):
                self.run_once(runtime, proof, child)

    def test_linked_evidence_source_hash_must_match_prediction_payload(self):
        for name, folder in (("entry", "paper_ledger"), ("dna", "anomaly_logs")):
            with self.subTest(linked=name):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    runtime, proof = root / "runtime", root / "proof"
                    runtime.mkdir()
                    def child(*args, **kwargs):
                        digest = make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                        filename = ("entry_" if name == "entry" else "dna_") + digest + ".json"
                        path = runtime / "data" / folder / filename
                        evidence = json.loads(path.read_text(encoding="utf-8"))
                        evidence["source_hash"] = "b" * 64
                        path.write_text(json.dumps(evidence), encoding="utf-8")
                        return SimpleNamespace(returncode=0)
                    with self.assertRaisesRegex(RuntimeError, "LINKED_EVIDENCE_INVALID"):
                        self.run_once(runtime, proof, child)

    def test_missing_or_invalid_source_hash_fails_closed(self):
        for value in (None, "", "not-a-sha256"):
            with self.subTest(value=value):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    runtime, proof = root / "runtime", root / "proof"
                    runtime.mkdir()
                    def child(*args, **kwargs):
                        make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                        path = runtime / "data" / "paper_ledger" / "receipt.json"
                        receipt = json.loads(path.read_text(encoding="utf-8"))
                        receipt["source_hash"] = value
                        path.write_text(json.dumps(receipt), encoding="utf-8")
                        return SimpleNamespace(returncode=0)
                    with self.assertRaisesRegex(RuntimeError, "SOURCE_PROVENANCE_MISMATCH"):
                        self.run_once(runtime, proof, child)


    def test_missing_raw_snapshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            def child(*args, **kwargs):
                make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                (runtime / "data" / "raw_snapshot.json").unlink()
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "RAW_SNAPSHOT_MISSING"):
                self.run_once(runtime, proof, child)

    def test_raw_snapshot_bytes_must_match_prediction_source_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            def child(*args, **kwargs):
                make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                path = runtime / "data" / "raw_snapshot.json"
                path.write_bytes(path.read_bytes() + b"tampered")
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "RAW_SNAPSHOT_HASH_MISMATCH"):
                self.run_once(runtime, proof, child)

    def test_raw_snapshot_capture_time_must_match_prediction_source_time(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            def child(*args, **kwargs):
                make_receipt(runtime, datetime.now(timezone.utc).isoformat(),
                             source_captured_at=old)
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "RAW_SNAPSHOT_TIMESTAMP_MISMATCH"):
                self.run_once(runtime, proof, child)


    def test_stale_source_timestamp_even_with_fresh_receipt_fails_closed(self):
        # The prior guard only compared raw captured_at with payload source_timestamp.
        # Both could agree on an old snapshot while created_at was current.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            stale = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            def child(*args, **kwargs):
                make_receipt(runtime, datetime.now(timezone.utc).isoformat(),
                             source_captured_at=stale, payload_source_at=stale)
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "RAW_SNAPSHOT_NOT_FROM_CURRENT_RUN"):
                self.run_once(runtime, proof, child)

    def test_future_source_timestamp_even_with_fresh_receipt_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            def child(*args, **kwargs):
                make_receipt(runtime, datetime.now(timezone.utc).isoformat(),
                             source_captured_at=future, payload_source_at=future)
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "RAW_SNAPSHOT_NOT_FROM_CURRENT_RUN"):
                self.run_once(runtime, proof, child)

    def test_naive_source_timestamp_even_with_fresh_receipt_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            naive = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            def child(*args, **kwargs):
                make_receipt(runtime, datetime.now(timezone.utc).isoformat(),
                             source_captured_at=naive, payload_source_at=naive)
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "RAW_SNAPSHOT_TIMESTAMP_INVALID"):
                self.run_once(runtime, proof, child)


    def test_synthetic_source_kind_cannot_be_certified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            def child(*args, **kwargs):
                make_receipt(runtime, datetime.now(timezone.utc).isoformat(),
                             source_kind="TEST_FIXTURE_ONLY")
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "SOURCE_KIND_NOT_BROKER_READONLY"):
                self.run_once(runtime, proof, child)

    def test_prediction_provenance_cannot_disagree_with_raw_source_kind(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            def child(*args, **kwargs):
                make_receipt(runtime, datetime.now(timezone.utc).isoformat(),
                             payload_source_kind="TEST_FIXTURE_ONLY")
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "SOURCE_KIND_PROVENANCE_MISMATCH"):
                self.run_once(runtime, proof, child)

    def test_empty_raw_quote_list_cannot_be_certified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            def child(*args, **kwargs):
                make_receipt(runtime, datetime.now(timezone.utc).isoformat(),
                             quotes=[])
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "RAW_SNAPSHOT_QUOTES_MISSING"):
                self.run_once(runtime, proof, child)

    def test_explicit_forbidden_order_flag_in_receipt_fails_closed(self):
        # Optional legacy field must never override PAPER safety when present.
        for value in (1, True, "0", None):
            with self.subTest(value=value):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    runtime, proof = root / "runtime", root / "proof"
                    runtime.mkdir()
                    def child(*args, **kwargs):
                        make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                        path = runtime / "data" / "paper_ledger" / "receipt.json"
                        receipt = json.loads(path.read_text(encoding="utf-8"))
                        receipt["real_broker_orders"] = value
                        path.write_text(json.dumps(receipt), encoding="utf-8")
                        return SimpleNamespace(returncode=0)
                    with self.assertRaisesRegex(RuntimeError, "RECEIPT_SAFETY_FAILURE"):
                        self.run_once(runtime, proof, child)

    def test_explicit_forbidden_order_flag_in_linked_evidence_fails_closed(self):
        for folder, prefix in (("paper_ledger", "entry_"), ("anomaly_logs", "dna_")):
            for value in (1, True, "0", None):
                with self.subTest(folder=folder, value=value):
                    with tempfile.TemporaryDirectory() as temp:
                        root = Path(temp)
                        runtime, proof = root / "runtime", root / "proof"
                        runtime.mkdir()
                        def child(*args, **kwargs):
                            digest = make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                            path = runtime / "data" / folder / (prefix + digest + ".json")
                            evidence = json.loads(path.read_text(encoding="utf-8"))
                            evidence["real_broker_orders"] = value
                            path.write_text(json.dumps(evidence), encoding="utf-8")
                            return SimpleNamespace(returncode=0)
                        with self.assertRaisesRegex(RuntimeError, "LINKED_EVIDENCE_INVALID"):
                            self.run_once(runtime, proof, child)

if __name__ == "__main__":
    unittest.main()
