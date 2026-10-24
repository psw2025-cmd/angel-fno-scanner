"""Offline regression: PAPER entry ledger must bind to the exact ranked contracts.

These fixtures are synthetic. No broker authentication, orders, or deployment.
"""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import test_cloud_paper_receipt_freshness as fixtures


def entry_contracts(payload):
    return [
        {**rank, "underlying": rank["symbol"],
         "captured_at": rank["entry_captured_at"]}
        for rank in payload["ranking"]
    ]


class EntryLedgerBindingTests(unittest.TestCase):
    def run_case(self, mutation=None, *, reject=False):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, proof = Path(tmp) / "runtime", Path(tmp) / "proof"
            runtime.mkdir()

            def child(*args, **kwargs):
                digest = fixtures.make_receipt(
                    runtime, datetime.now(timezone.utc).isoformat()
                )
                receipt = json.loads(
                    (runtime / "data" / "paper_ledger" / "receipt.json").read_text()
                )
                payload = json.loads(receipt["bigquery_merge_parameters"]["payload"])
                entry_path = runtime / "data" / "paper_ledger" / ("entry_" + digest + ".json")
                entry = json.loads(entry_path.read_text())
                entry["contracts"] = entry_contracts(payload)
                if mutation is not None:
                    mutation(entry)
                entry_path.write_text(json.dumps(entry), encoding="utf-8")
                return SimpleNamespace(returncode=0)

            if reject:
                with self.assertRaisesRegex(RuntimeError, "ENTRY_LEDGER_CONTRACT_MISMATCH"):
                    fixtures.CurrentRunReceiptTests().run_once(runtime, proof, child)
                self.assertNotEqual(
                    json.loads((proof / "status.json").read_text())["status"],
                    "PAPER_RECEIPT_VERIFIED",
                )
            else:
                self.assertEqual(
                    fixtures.CurrentRunReceiptTests().run_once(runtime, proof, child), 0
                )

    def test_matching_entry_contract_is_valid_internal_evidence(self):
        self.run_case()

    def test_forged_entry_strike_must_fail(self):
        self.run_case(
            lambda e: e["contracts"][0].__setitem__("strike", 99999.0), reject=True
        )

    def test_forged_entry_price_must_fail(self):
        self.run_case(
            lambda e: e["contracts"][0].__setitem__("entry_price", 999.0), reject=True
        )

    def test_missing_contract_manifest_must_fail(self):
        self.run_case(lambda e: e.pop("contracts"), reject=True)

    def test_empty_contract_manifest_must_fail(self):
        self.run_case(lambda e: e.__setitem__("contracts", []), reject=True)

    def test_duplicate_contract_manifest_must_fail(self):
        self.run_case(
            lambda e: e["contracts"].append(dict(e["contracts"][0])), reject=True
        )


if __name__ == "__main__":
    unittest.main()
