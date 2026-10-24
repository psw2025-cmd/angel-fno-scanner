"""Offline guard: PAPER receipt must not falsely claim BigQuery insertion.

No network, broker, database or order operations. Synthetic receipts only.
"""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from cloud_runner import main as runner
from test_cloud_paper_receipt_freshness import CurrentRunReceiptTests, make_receipt

EXPECTED_TABLE = "fno-angel-prod-1790444589.PAPER_TRADING_SANDBOX_PHASE2.prediction_ledger"
EXPECTED_SOURCE = "ANGEL_SMARTAPI_READONLY_QUOTES_NOT_OFFICIAL_SETTLEMENT"


def valid_metadata():
    return {
        "source_kind": EXPECTED_SOURCE,
        "destination_table": EXPECTED_TABLE,
        "bigquery_insert_id": None,
        "bigquery_job_id": None,
    }


class PaperReceiptClaimTests(unittest.TestCase):
    def test_destination_contract_tracks_reviewed_phase2_writer(self):
        from run_phase2_local import TABLE
        self.assertEqual(TABLE, EXPECTED_TABLE)

    def test_valid_local_only_metadata(self):
        receipt = {"status": "LOCAL_ARTIFACT_ONLY_NOT_INSERTED", **valid_metadata()}
        self.assertTrue(runner.validate_paper_receipt_metadata(receipt))

    def test_reject_false_bigquery_write_receipts(self):
        for field in ("bigquery_insert_id", "bigquery_job_id"):
            for value in ("claimed-write-id", 0, False):
                with self.subTest(field=field, value=value):
                    receipt = {"status": "LOCAL_ARTIFACT_ONLY_NOT_INSERTED", **valid_metadata()}
                    receipt[field] = value
                    with self.assertRaisesRegex(RuntimeError, "RECEIPT_METADATA_INVALID"):
                        runner.validate_paper_receipt_metadata(receipt)

    def test_reject_missing_and_wrong_destination_or_source(self):
        for field, value in (
            ("destination_table", "fno-angel-prod-1790444589.OTHER.ledger"),
            ("destination_table", ""),
            ("source_kind", "TEST_FIXTURE_ONLY"),
            ("source_kind", ""),
        ):
            with self.subTest(field=field, value=value):
                receipt = {"status": "LOCAL_ARTIFACT_ONLY_NOT_INSERTED", **valid_metadata()}
                receipt[field] = value
                with self.assertRaisesRegex(RuntimeError, "RECEIPT_METADATA_INVALID"):
                    runner.validate_paper_receipt_metadata(receipt)
        for field in valid_metadata():
            with self.subTest(missing=field):
                receipt = {"status": "LOCAL_ARTIFACT_ONLY_NOT_INSERTED", **valid_metadata()}
                del receipt[field]
                with self.assertRaisesRegex(RuntimeError, "RECEIPT_METADATA_INVALID"):
                    runner.validate_paper_receipt_metadata(receipt)

    def test_reject_non_dict_metadata(self):
        for value in (None, [], "receipt", 42):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "RECEIPT_METADATA_INVALID"):
                    runner.validate_paper_receipt_metadata(value)

    def test_full_runner_rejects_false_insert_or_wrong_destination(self):
        for field, value in (
            ("bigquery_insert_id", "fabricated-insert"),
            ("destination_table", "fno-angel-prod-1790444589.OTHER.ledger"),
        ):
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    runtime, proof = root / "runtime", root / "proof"
                    runtime.mkdir()

                    def child(*args, **kwargs):
                        make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                        path = runtime / "data" / "paper_ledger" / "receipt.json"
                        receipt = json.loads(path.read_text(encoding="utf-8"))
                        receipt.update(valid_metadata())
                        receipt[field] = value
                        path.write_text(json.dumps(receipt), encoding="utf-8")
                        return SimpleNamespace(returncode=0)

                    with self.assertRaisesRegex(RuntimeError, "RECEIPT_METADATA_INVALID"):
                        CurrentRunReceiptTests().run_once(runtime, proof, child)
                    status = json.loads((proof / "status.json").read_text(encoding="utf-8"))
                    self.assertNotEqual(status["status"], "PAPER_RECEIPT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
