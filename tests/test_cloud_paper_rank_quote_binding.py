"""Fail-closed offline regression: every PAPER rank must reference a captured quote.

This checks internal provenance only; fixtures do not authenticate broker quotes,
market prices, fills, cloud deployment, or absence of real orders.
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


def quotes():
    return [{"contract": {"tradingsymbol": "OFFLINE_TEST_ONLY", "symboltoken": "999"},
             "quote": {"tradingSymbol": "OFFLINE_TEST_ONLY", "symbolToken": "999"}}]


class RankQuoteBindingTests(unittest.TestCase):
    def test_matching_rank_has_quote_identity(self):
        self.assertTrue(runner.validate_ranking_quote_binding(
            {"ranking": [valid_rank()]}, quotes()))

    def test_ranked_contract_not_in_snapshot_fails_closed(self):
        for changed in (
            {"tradingsymbol": "NOT_IN_CAPTURE"},
            {"symboltoken": "998"},
        ):
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(RuntimeError, "RANK_QUOTE_IDENTITY_MISMATCH"):
                    runner.validate_ranking_quote_binding(
                        {"ranking": [{**valid_rank(), **changed}]}, quotes())

    def test_ranked_contract_cannot_reuse_one_quote_under_other_strike(self):
        second = {**valid_rank(2), "strike": 24100.0}
        with self.assertRaisesRegex(RuntimeError, "RANK_QUOTE_DUPLICATE"):
            runner.validate_ranking_quote_binding(
                {"ranking": [valid_rank(), second]}, quotes())

    def test_missing_or_malformed_quote_contract_is_not_accepted(self):
        for bad in ([], [{}], [{"contract": {"tradingsymbol": "OFFLINE_TEST_ONLY"}}]):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(RuntimeError, "RANK_QUOTE_IDENTITY_MISMATCH"):
                    runner.validate_ranking_quote_binding(
                        {"ranking": [valid_rank()]}, bad)

    def test_hash_consistent_forged_rank_does_not_publish_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "runtime"
            proof = Path(tmp) / "proof"
            runtime.mkdir()
            def child(*args, **kwargs):
                emit_hash_consistent_unsafe_payload(
                    runtime, {"ranking": [{**valid_rank(), "tradingsymbol": "NOT_IN_CAPTURE"}]})
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "RANK_QUOTE_IDENTITY_MISMATCH"):
                CurrentRunReceiptTests().run_once(runtime, proof, child)
            status = json.loads((proof / "status.json").read_text(encoding="utf-8"))
            self.assertNotEqual(status["status"], "PAPER_RECEIPT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
