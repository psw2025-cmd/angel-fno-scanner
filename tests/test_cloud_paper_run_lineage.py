"""Synthetic end-to-end regression: PAPER run lineage must match captured source.

All artifacts are temporary test fixtures. This does not authenticate Angel
SmartAPI, prove a live market session, or authorize broker orders.
"""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import test_cloud_paper_receipt_freshness as fixtures
from phase2.daily_close import canonical_hash


def rewrite_hash_consistent_payload(runtime, mutate):
    """Change prediction fields and recompute every dependent local digest."""
    receipt_path = runtime / "data" / "paper_ledger" / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload = json.loads(receipt["bigquery_merge_parameters"]["payload"])
    old_hash = payload["prediction_hash"]
    mutate(payload)
    payload.pop("prediction_hash", None)
    new_hash = canonical_hash(payload)
    payload["prediction_hash"] = new_hash
    receipt["prediction_hash"] = new_hash
    receipt["bigquery_merge_parameters"]["hash"] = new_hash
    receipt["bigquery_merge_parameters"]["payload"] = json.dumps(payload, sort_keys=True)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    for folder, prefix in (("paper_ledger", "entry_"), ("anomaly_logs", "dna_")):
        original = runtime / "data" / folder / (prefix + old_hash + ".json")
        linked = json.loads(original.read_text(encoding="utf-8"))
        linked["prediction_hash"] = new_hash
        original.unlink()
        (original.parent / (prefix + new_hash + ".json")).write_text(
            json.dumps(linked), encoding="utf-8"
        )


class PaperRunLineageTests(unittest.TestCase):
    def run_case(self, mutate=None, expected=None):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, proof = Path(tmp) / "runtime", Path(tmp) / "proof"
            runtime.mkdir()

            def child(*args, **kwargs):
                fixtures.make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                if mutate is not None:
                    rewrite_hash_consistent_payload(runtime, mutate)
                return SimpleNamespace(returncode=0)

            if expected is None:
                self.assertEqual(
                    fixtures.CurrentRunReceiptTests().run_once(runtime, proof, child), 0
                )
                self.assertEqual(
                    json.loads((proof / "status.json").read_text())["status"],
                    "PAPER_RECEIPT_VERIFIED",
                )
            else:
                with self.assertRaisesRegex(RuntimeError, expected):
                    fixtures.CurrentRunReceiptTests().run_once(runtime, proof, child)
                self.assertNotEqual(
                    json.loads((proof / "status.json").read_text())["status"],
                    "PAPER_RECEIPT_VERIFIED",
                )

    def test_matching_run_lineage_remains_accepted(self):
        self.run_case()

    def test_missing_run_id_fails_even_with_rehashed_receipt(self):
        self.run_case(lambda p: p.pop("run_id"), "PREDICTION_LINEAGE_INVALID")

    def test_unrelated_run_id_fails_even_with_rehashed_receipt(self):
        self.run_case(lambda p: p.__setitem__("run_id", "f" * 64),
                      "PREDICTION_RUN_ID_MISMATCH")

    def test_missing_or_malformed_features_digest_fails(self):
        for value in (None, "not-a-digest", "A" * 64):
            with self.subTest(value=value):
                self.run_case(lambda p, v=value: p.__setitem__("features_hash", v),
                              "PREDICTION_LINEAGE_INVALID")

    def test_missing_or_malformed_model_version_fails(self):
        for value in (None, "", "  ", 42):
            with self.subTest(value=value):
                self.run_case(lambda p, v=value: p.__setitem__("model_version", v),
                              "PREDICTION_LINEAGE_INVALID")


if __name__ == "__main__":
    unittest.main()
