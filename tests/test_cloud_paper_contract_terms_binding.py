"""Offline negative tests: a ranked option must match captured contract terms.

All fixtures are synthetic. No authenticated feed, broker orders or cloud runtime.
"""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from cloud_runner import main as runner
from test_cloud_paper_ranking_contract import valid_rank
from test_cloud_paper_payload_authority import emit_hash_consistent_unsafe_payload
from test_cloud_paper_receipt_freshness import CurrentRunReceiptTests


def captured():
    return [{"contract": {
        "underlying": "NIFTY", "expiry": "2026-10-29",
        "strike": 24000.0, "option_type": "CE",
        "tradingsymbol": "OFFLINE_TEST_ONLY", "symboltoken": "999",
    }, "quote": {"tradingSymbol": "OFFLINE_TEST_ONLY", "symbolToken": "999"}}]


class ContractTermsBindingTests(unittest.TestCase):
    def test_matching_terms_are_accepted(self):
        self.assertTrue(runner.validate_ranking_contract_terms(
            {"ranking": [valid_rank()]}, captured()))

    def test_wrong_underlying_expiry_strike_or_side_rejected(self):
        for changed in ({"symbol": "BANKNIFTY"}, {"expiry": "2026-11-05"},
                        {"strike": 24100.0}, {"option_type": "PE"}):
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(RuntimeError, "RANK_QUOTE_CONTRACT_TERMS_MISMATCH"):
                    runner.validate_ranking_contract_terms(
                        {"ranking": [{**valid_rank(), **changed}]}, captured())

    def test_missing_contract_metadata_fails_closed(self):
        for missing in ("underlying", "expiry", "strike", "option_type"):
            with self.subTest(missing=missing):
                rows = captured()
                del rows[0]["contract"][missing]
                with self.assertRaisesRegex(RuntimeError, "RANK_QUOTE_CONTRACT_TERMS_MISMATCH"):
                    runner.validate_ranking_contract_terms(
                        {"ranking": [valid_rank()]}, rows)

    def test_full_runner_rejects_hash_consistent_wrong_underlying(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, proof = Path(tmp) / "runtime", Path(tmp) / "proof"
            runtime.mkdir()
            def child(*args, **kwargs):
                emit_hash_consistent_unsafe_payload(
                    runtime, {"ranking": [{**valid_rank(), "symbol": "BANKNIFTY"}]})
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "RANK_QUOTE_CONTRACT_TERMS_MISMATCH"):
                CurrentRunReceiptTests().run_once(runtime, proof, child)
            self.assertNotEqual(
                json.loads((proof / "status.json").read_text())["status"],
                "PAPER_RECEIPT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
