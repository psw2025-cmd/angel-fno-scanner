"""Offline regression: ranked PAPER entry bid/ask must match captured quote depth.

All snapshots here are synthetic; no broker authentication, execution, or live orders.
"""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from cloud_runner import main as runner
from test_cloud_paper_ranking_contract import valid_rank
from test_cloud_paper_receipt_freshness import CurrentRunReceiptTests, make_receipt


def captured_quote(bid=100.0, ask=101.0):
    return [{"contract": {"tradingsymbol": "OFFLINE_TEST_ONLY", "symboltoken": "999"},
             "quote": {"tradingSymbol": "OFFLINE_TEST_ONLY", "symbolToken": "999",
                       "depth": {"buy": [{"price": bid}], "sell": [{"price": ask}]}}}]


class QuotePriceBindingTests(unittest.TestCase):
    def test_matching_depth_passes(self):
        self.assertTrue(runner.validate_ranking_quote_prices(
            {"ranking": [valid_rank()]}, captured_quote()))

    def test_mismatched_bid_or_ask_fails_closed(self):
        for bid, ask in ((99.0, 101.0), (100.0, 102.0)):
            with self.subTest(bid=bid, ask=ask):
                with self.assertRaisesRegex(RuntimeError, "RANK_QUOTE_PRICE_MISMATCH"):
                    runner.validate_ranking_quote_prices(
                        {"ranking": [valid_rank()]}, captured_quote(bid, ask))

    def test_missing_or_invalid_depth_fails_closed(self):
        for bad in (None, {}, {"buy": [], "sell": [{"price": 101}]},
                    {"buy": [{"price": 100}], "sell": []},
                    {"buy": [{"price": float("nan")}], "sell": [{"price": 101}]},
                    {"buy": [{"price": 102}], "sell": [{"price": 101}]},
                    {"buy": [{"price": True}], "sell": [{"price": 101}]}):
            with self.subTest(depth=bad):
                quotes = captured_quote()
                quotes[0]["quote"]["depth"] = bad
                with self.assertRaisesRegex(RuntimeError, "RANK_QUOTE_DEPTH_INVALID"):
                    runner.validate_ranking_quote_prices(
                        {"ranking": [valid_rank()]}, quotes)

    def test_hash_consistent_forged_entry_price_fails_full_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, proof = Path(tmp) / "runtime", Path(tmp) / "proof"
            runtime.mkdir()
            def child(*args, **kwargs):
                # The receipt and hashes are self-consistent, but the entry bid
                # is inconsistent with the captured quote depth.
                make_receipt(runtime, datetime.now(timezone.utc).isoformat(),
                             ranking=[{**valid_rank(), "entry_bid": 99.0}])
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "RANK_QUOTE_PRICE_MISMATCH"):
                CurrentRunReceiptTests().run_once(runtime, proof, child)
            self.assertNotEqual(
                json.loads((proof / "status.json").read_text())["status"],
                "PAPER_RECEIPT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
